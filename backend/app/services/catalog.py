"""Catalogo publico + admin menu. Cache Redis 10 min + invalidacion reactiva."""

import json
import logging
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.infrastructure.redis import cache_delete, cache_get, cache_set
from app.models.restaurant import Modifier, ModifierGroup, Product, Restaurant

MENU_TTL = 600
RESTAURANTS_TTL = 600
logger = logging.getLogger(__name__)


def _menu_key(rid: UUID | str) -> str:
    return f"cache:menu:{rid}"


async def invalidate_menu(restaurant_id: UUID | str) -> None:
    try:
        await cache_delete(_menu_key(restaurant_id))
        await cache_delete("cache:restaurants:active")
    except Exception:
        logger.exception("No se pudo invalidar la cache del catalogo")


def _product_available(p: Product) -> bool:
    if not p.is_available:
        return False
    if p.track_stock and p.stock is not None and p.stock <= 0:
        return False
    return True


def _serialize_menu(restaurant: Restaurant) -> dict:
    cats = sorted(restaurant.categories, key=lambda c: c.sort_order)
    return {
        "restaurant_id": str(restaurant.id),
        "restaurant_name": restaurant.name,
        "categories": [
            {"id": str(c.id), "name": c.name, "sort_order": c.sort_order, "is_active": c.is_active}
            for c in cats
            if c.is_active
        ],
        "products": [
            {
                "id": str(p.id),
                "category_id": str(p.category_id),
                "name": p.name,
                "description": p.description,
                "base_price": str(p.base_price),
                "image_url": p.image_url,
                "is_available": _product_available(p),
                "track_stock": p.track_stock,
                "stock": p.stock,
                "modifier_groups": [
                    {
                        "id": str(g.id),
                        "name": g.name,
                        "min_selectable": g.min_selectable,
                        "max_selectable": g.max_selectable,
                        "is_required": g.min_selectable >= 1,
                        "modifiers": [
                            {
                                "id": str(m.id),
                                "name": m.name,
                                "extra_price": str(m.extra_price),
                                "is_available": m.is_available
                                and not (m.track_stock and m.stock is not None and m.stock <= 0),
                            }
                            for m in g.modifiers
                        ],
                    }
                    for g in p.modifier_groups
                ],
            }
            for p in restaurant.products
        ],
    }


async def get_menu(db: AsyncSession, restaurant_id: UUID) -> dict:
    cached = await cache_get(_menu_key(restaurant_id))
    if cached:
        return json.loads(cached)
    stmt = (
        select(Restaurant)
        .where(Restaurant.id == restaurant_id, Restaurant.is_active.is_(True))
        .options(
            selectinload(Restaurant.categories),
            selectinload(Restaurant.products)
            .selectinload(Product.modifier_groups)
            .selectinload(ModifierGroup.modifiers),
        )
    )
    restaurant = (await db.execute(stmt)).scalar_one_or_none()
    if restaurant is None:
        raise AppException("RESTAURANT_NOT_FOUND", "Restaurante no encontrado.", 404)
    data = _serialize_menu(restaurant)
    await cache_set(_menu_key(restaurant_id), json.dumps(data), MENU_TTL)
    return data


async def list_restaurants(db: AsyncSession, only_open: bool = True) -> list[dict]:
    cached = await cache_get("cache:restaurants:active")
    if cached:
        return json.loads(cached)
    stmt = select(Restaurant).where(Restaurant.is_active.is_(True))
    if only_open:
        stmt = stmt.where(Restaurant.is_open.is_(True))
    stmt = stmt.order_by(Restaurant.name)
    rows = (await db.execute(stmt)).scalars().all()
    data = [
        {
            "id": str(r.id),
            "name": r.name,
            "phone_number": r.phone_number,
            "address": r.address,
            "commission_rate": str(r.commission_rate),
            "is_open": r.is_open,
            "is_active": r.is_active,
        }
        for r in rows
    ]
    await cache_set("cache:restaurants:active", json.dumps(data), RESTAURANTS_TTL)
    return data


async def create_restaurant(
    db: AsyncSession,
    name: str,
    phone: str,
    address: str,
    lat: Decimal,
    lon: Decimal,
    commission: Decimal = Decimal("15.00"),
) -> Restaurant:
    r = Restaurant(
        id=uuid4(),
        name=name,
        phone_number=phone,
        address=address,
        location=f"POINT({lon} {lat})",
        commission_rate=commission,
    )
    db.add(r)
    await db.commit()
    await invalidate_menu(r.id)
    return r


async def patch_product(db: AsyncSession, product_id: UUID, fields: dict) -> Product:
    stmt = select(Product).where(Product.id == product_id)
    product = (await db.execute(stmt)).scalar_one_or_none()
    if product is None:
        raise AppException("PRODUCT_NOT_FOUND", "Producto no encontrado.", 404)
    allowed = {
        "name",
        "description",
        "base_price",
        "image_url",
        "is_available",
        "track_stock",
        "stock",
        "category_id",
    }
    for k, v in fields.items():
        if k in allowed and v is not None:
            setattr(product, k, v)
    if product.track_stock and (product.stock is None or product.stock < 0):
        raise AppException("INVALID_STOCK_CONFIG", "Stock invalido para track_stock=true.", 422)
    # Auto-apagado al llegar a 0
    if product.track_stock and product.stock == 0:
        product.is_available = False
    await db.commit()
    await invalidate_menu(product.restaurant_id)
    return product


async def patch_modifier(db: AsyncSession, modifier_id: UUID, fields: dict) -> Modifier:
    stmt = select(Modifier).where(Modifier.id == modifier_id)
    modifier = (await db.execute(stmt)).scalar_one_or_none()
    if modifier is None:
        raise AppException("MODIFIER_NOT_FOUND", "Modificador no encontrado.", 404)
    allowed = {"name", "extra_price", "is_available", "track_stock", "stock"}
    for k, v in fields.items():
        if k in allowed and v is not None:
            setattr(modifier, k, v)
    await db.commit()
    # Invalida menu del restaurante padre
    gstmt = select(ModifierGroup).where(ModifierGroup.id == modifier.group_id)
    group = (await db.execute(gstmt)).scalar_one_or_none()
    if group:
        p = (
            await db.execute(select(Product).where(Product.id == group.product_id))
        ).scalar_one_or_none()
        if p:
            await invalidate_menu(p.restaurant_id)
    return modifier


async def validate_modifiers_for_draft(
    db: AsyncSession, product: Product, modifier_ids: list[UUID]
) -> list[Modifier]:
    """Valida pertenencia, disponibilidad y min/max por grupo. RF-CAT-07."""
    if not modifier_ids:
        # Verifica que no haya grupos obligatorios
        gstmt = select(ModifierGroup).where(ModifierGroup.product_id == product.id)
        required_groups = list((await db.execute(gstmt)).scalars().all())
        for g in required_groups:
            if g.min_selectable >= 1:
                raise AppException(
                    "MODIFIERS_REQUIRED",
                    f"El grupo '{g.name}' requiere al menos {g.min_selectable}.",
                    422,
                )
        return []
    stmt = (
        select(Modifier).where(Modifier.id.in_(modifier_ids)).options(selectinload(Modifier.group))
    )
    mods = list((await db.execute(stmt)).scalars().all())
    if len(mods) != len(set(modifier_ids)):
        raise AppException("MODIFIER_NOT_FOUND", "Un modificador no existe.", 422)
    # Agrupa por grupo
    by_group: dict[UUID, list[Modifier]] = {}
    for m in mods:
        if m.group.product_id != product.id:
            raise AppException(
                "MODIFIER_MISMATCH", f"'{m.name}' no pertenece a este producto.", 422
            )
        if not m.is_available or (m.track_stock and m.stock is not None and m.stock <= 0):
            raise AppException("MODIFIER_UNAVAILABLE", f"'{m.name}' no disponible.", 409)
        by_group.setdefault(m.group_id, []).append(m)
    # Valida min/max contra grupos del producto
    gstmt = select(ModifierGroup).where(ModifierGroup.product_id == product.id)
    groups_by_id = {g.id: g for g in (await db.execute(gstmt)).scalars().all()}
    for gid, selected in by_group.items():
        selected_group = groups_by_id.get(gid)
        if selected_group is None:
            raise AppException("MODIFIER_MISMATCH", "Grupo invalido.", 422)
        n = len(selected)
        if not (selected_group.min_selectable <= n <= selected_group.max_selectable):
            raise AppException(
                "MODIFIER_CONSTRAINT",
                f"'{selected_group.name}': elige entre "
                f"{selected_group.min_selectable} y {selected_group.max_selectable}.",
                422,
            )
    # Verifica obligatorios faltantes
    for gid, g in groups_by_id.items():
        if g.min_selectable >= 1 and gid not in by_group:
            raise AppException("MODIFIERS_REQUIRED", f"'{g.name}' es obligatorio.", 422)
    return mods
