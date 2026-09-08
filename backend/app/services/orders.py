"""Motor transaccional: draft + reserva atomica 15 min, cancel, transiciones.

RF-CAT-07..11, RF-PAY-01..11
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.domain.financial import money
from app.domain.states import OrderStatus, transition
from app.models.financial import ExchangeRate
from app.models.order import Order, OrderItem, OrderModifier, OrderReservation, OrderStatusEnum
from app.models.restaurant import Modifier, Product, Restaurant
from app.models.user import User, UserAddress
from app.services import pricing as pricing_service
from app.services.events import record_order_event

logger = logging.getLogger(__name__)


def _order_number() -> str:
    # SJM-YYYY-NNNN (unicidad garantizada por constraint; reintento en servicio)
    now = datetime.now(UTC)
    return f"SJM-{now.year}-{uuid4().hex[:6].upper()}"


def _parse_point_wkt(wkt: str) -> tuple[Decimal, Decimal]:
    m = re.match(r"POINT\(([-\d.]+) ([-\d.]+)\)", wkt)
    if not m:
        raise AppException("INVALID_LOCATION", "Ubicacion invalida.", 422)
    lon, lat = Decimal(m.group(1)), Decimal(m.group(2))
    return lat, lon


def _haversine_m(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> Decimal:
    import math

    r = 6371000.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2 - lat1))
    dlambda = math.radians(float(lon2 - lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return Decimal(str(2 * r * math.asin(math.sqrt(a)))).quantize(Decimal("0.01"))


async def create_draft(
    db: AsyncSession,
    customer: User,
    items: list[dict],
    address_id: UUID,
) -> Order:
    if not customer.full_name.strip():
        raise AppException(
            "PROFILE_INCOMPLETE", "Completa tu nombre antes de crear un pedido.", 409
        )
    # 1. Direccion propia
    addr = (
        await db.execute(select(UserAddress).where(UserAddress.id == address_id))
    ).scalar_one_or_none()
    if addr is None or addr.user_id != customer.id:
        raise AppException("ADDRESS_NOT_OWNED", "Direccion no valida.", 403)
    if not items:
        raise AppException("EMPTY_CART", "Carrito vacio.", 422)

    # 2. Carga productos y valida mismo restaurante
    product_ids = [UUID(i["product_id"]) for i in items]
    products = {
        p.id: p
        for p in (await db.execute(select(Product).where(Product.id.in_(product_ids))))
        .scalars()
        .all()
    }
    if len(products) != len(set(product_ids)):
        raise AppException("PRODUCT_NOT_FOUND", "Un producto no existe.", 404)
    restaurant_ids = {p.restaurant_id for p in products.values()}
    if len(restaurant_ids) != 1:
        raise AppException("MULTI_RESTAURANT", "Un pedido, un restaurante.", 422)
    restaurant_id = next(iter(restaurant_ids))
    restaurant = (
        await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    ).scalar_one_or_none()
    if restaurant is None or not restaurant.is_active or not restaurant.is_open:
        raise AppException("RESTAURANT_CLOSED", "Restaurante no disponible.", 409)

    # 3. Tasa + fees config (bloquea checkout si faltan)
    rate_row: ExchangeRate = await pricing_service.get_valid_rate(db)
    platform_fee = await pricing_service.get_platform_fee(db)

    # 4. Distancia (haversine; PostGIS ST_DistanceSphere en prod con geoalchemy)
    r_lat, r_lon = _parse_point_wkt(restaurant.location)
    a_lat, a_lon = _parse_point_wkt(addr.location)
    distance_m = _haversine_m(r_lat, r_lon, a_lat, a_lon)
    delivery_fee, _tier_id = await pricing_service.get_delivery_fee(db, distance_m)

    # 5. Reserva atomica + calculo en UNA transaccion
    # Bloquea filas producto
    for pid in product_ids:
        await db.execute(select(Product).where(Product.id == pid).with_for_update())

    subtotal = Decimal("0")
    lines: list[tuple[Product, int, list[Modifier], Decimal]] = []
    reservation_items: list[dict] = []
    for entry in items:
        pid = UUID(entry["product_id"])
        qty = int(entry["quantity"])
        if not (1 <= qty <= 99):
            raise AppException("INVALID_QUANTITY", "Cantidad 1..99.", 422)
        product = products[pid]
        if not product.is_available:
            raise AppException("PRODUCT_UNAVAILABLE", f"'{product.name}' no disponible.", 409)
        mod_ids = [UUID(m) for m in entry.get("modifier_ids", [])]
        line_total_val, mods = await pricing_service.compute_line(db, product, qty, mod_ids)
        subtotal += line_total_val
        lines.append((product, qty, mods, line_total_val))
        # Reserva stock
        reserved = 0
        if product.track_stock:
            if product.stock is None or product.stock < qty:
                raise AppException(
                    "INSUFFICIENT_STOCK",
                    f"Stock insuficiente de '{product.name}'.",
                    409,
                    {"product_id": str(pid), "available": product.stock, "requested": qty},
                )
            res = await db.execute(
                update(Product)
                .where(Product.id == pid, Product.stock >= qty)
                .values(stock=Product.stock - qty)
                .returning(Product.stock)
            )
            if res.scalar_one_or_none() is None:
                raise AppException(
                    "INSUFFICIENT_STOCK", f"Stock insuficiente de '{product.name}'.", 409
                )
            reserved = qty
        # Reserva modificadores con stock
        mod_reserved: dict[str, int] = {}
        for m in mods:
            if m.track_stock:
                if m.stock is None or m.stock < qty:
                    raise AppException(
                        "INSUFFICIENT_STOCK", f"Stock insuficiente de '{m.name}'.", 409
                    )
                r2 = await db.execute(
                    update(Modifier)
                    .where(Modifier.id == m.id, Modifier.stock >= qty)
                    .values(stock=Modifier.stock - qty)
                    .returning(Modifier.stock)
                )
                if r2.scalar_one_or_none() is None:
                    raise AppException(
                        "INSUFFICIENT_STOCK", f"Stock insuficiente de '{m.name}'.", 409
                    )
                mod_reserved[f"modifier_{m.id}_reserved"] = qty
        reservation_items.append(
            {
                "product_id": str(pid),
                "quantity": qty,
                "modifier_ids": [str(m.id) for m in mods],
                "reserved_stock": reserved,
                **mod_reserved,
            }
        )

    subtotal = money(subtotal)
    total = money(subtotal + delivery_fee + platform_fee)
    breakdown = pricing_service.build_payment_breakdown(total, rate_row.rate)
    expires = datetime.now(UTC) + timedelta(minutes=settings.RESERVATION_TTL_MINUTES)

    # 6. Crea orden + items + reserva
    order = Order(
        id=uuid4(),
        order_number=_order_number(),
        customer_id=customer.id,
        restaurant_id=restaurant_id,
        delivery_address_id=addr.id,
        status=OrderStatusEnum.PAYMENT_1_PENDING,
        subtotal_amount=subtotal,
        delivery_fee=delivery_fee,
        platform_fee=platform_fee,
        total_amount=total,
        first_half_amount=Decimal(breakdown["first_half"]),
        second_half_amount=Decimal(breakdown["second_half"]),
        total_ves_amount=Decimal(breakdown["total_ves"]),
        first_half_ves_amount=Decimal(breakdown["first_half_ves"]),
        second_half_ves_amount=Decimal(breakdown["second_half_ves"]),
        delivery_distance_m=distance_m,
        exchange_rate=rate_row.rate,
        exchange_rate_source=rate_row.source,
        exchange_rate_effective_date=str(rate_row.effective_date),
        exchange_rate_queried_at=rate_row.queried_at,
        quote_expires_at=expires,
        quote_snapshot={
            "items": [
                {
                    "product_id": str(p.id),
                    "name": p.name,
                    "base_price": str(p.base_price),
                    "quantity": q,
                    "modifiers": [
                        {"id": str(m.id), "name": m.name, "extra_price": str(m.extra_price)}
                        for m in mods
                    ],
                    "line_total": str(lt),
                }
                for p, q, mods, lt in lines
            ],
            "delivery_fee": str(delivery_fee),
            "platform_fee": str(platform_fee),
            "total": breakdown["total"],
            "first_half": breakdown["first_half"],
            "second_half": breakdown["second_half"],
            "first_half_ves": breakdown["first_half_ves"],
            "second_half_ves": breakdown["second_half_ves"],
            "exchange_rate": str(rate_row.rate),
            "distance_m": str(distance_m),
            "address": {
                "id": str(addr.id),
                "label": addr.label,
                "address_line": addr.address_line,
                "reference_point": addr.reference_point,
                "location": addr.location,
            },
        },
    )
    db.add(order)
    await db.flush()
    for p, q, mods, lt in lines:
        unit = money(lt / q)
        item = OrderItem(
            id=uuid4(),
            order_id=order.id,
            product_id=p.id,
            quantity=q,
            unit_price=unit,
            total_price=lt,
            product_snapshot={"name": p.name, "base_price": str(p.base_price)},
        )
        db.add(item)
        await db.flush()
        for m in mods:
            db.add(
                OrderModifier(
                    id=uuid4(),
                    order_item_id=item.id,
                    modifier_id=m.id,
                    modifier_name=m.name,
                    extra_price=m.extra_price,
                )
            )
    db.add(
        OrderReservation(
            id=uuid4(),
            order_id=order.id,
            expires_at=expires,
            status="ACTIVE",
            items=reservation_items,
        )
    )
    record_order_event(db, order, "ORDER_QUOTED")
    await db.commit()
    # Invalida cache menu (stock pudo cambiar)
    try:
        from app.services.catalog import invalidate_menu

        await invalidate_menu(restaurant_id)
    except Exception:
        logger.exception("No se pudo invalidar el menu tras reservar inventario")
    return order


async def cancel_draft(db: AsyncSession, order: Order, reason: str) -> Order:
    current = OrderStatus(order.status.value)
    transition(current, OrderStatus.CANCELLED)
    order.status = OrderStatusEnum.CANCELLED
    order.cancellation_reason = reason
    # Libera reserva si aun ACTIVE (no llego a PREPARING)
    stmt = select(OrderReservation).where(OrderReservation.order_id == order.id)
    res = (await db.execute(stmt)).scalar_one_or_none()
    if res is not None and res.status == "ACTIVE":
        res.status = "RELEASED"
        reserved_items: list[dict[str, Any]] = (
            cast(list[dict[str, Any]], res.items) if isinstance(res.items, list) else []
        )
        for it in reserved_items:
            pid = it.get("product_id")
            rs = it.get("reserved_stock", 0)
            if pid and rs:
                await db.execute(
                    update(Product)
                    .where(Product.id == UUID(str(pid)))
                    .values(stock=Product.stock + int(rs))
                )
            for modifier_id in it.get("modifier_ids", []) or []:
                modifier_reserved = int(it.get(f"modifier_{modifier_id}_reserved", 0) or 0)
                if modifier_reserved:
                    await db.execute(
                        update(Modifier)
                        .where(Modifier.id == UUID(str(modifier_id)))
                        .values(stock=Modifier.stock + modifier_reserved)
                    )
    record_order_event(db, order, "ORDER_CANCELLED")
    await db.commit()
    return order


async def get_order_detail(db: AsyncSession, order_id: UUID) -> Order:
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.modifiers),
            selectinload(Order.payments),
        )
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise AppException("ORDER_NOT_FOUND", "Pedido no encontrado.", 404)
    return order
