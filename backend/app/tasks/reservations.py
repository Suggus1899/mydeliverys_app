import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from celery import shared_task
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import get_db_context
from app.models.order import Order, OrderReservation, OrderStatusEnum
from app.models.restaurant import Modifier, Product


async def _expire_reservations_async() -> dict:
    now = datetime.now(UTC)
    expired_count = 0
    async with get_db_context() as db:
        stmt = (
            select(OrderReservation)
            .where(
                OrderReservation.status == "ACTIVE",
                OrderReservation.expires_at < now,
            )
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(stmt)
        expired_reservations = list(result.scalars().all())

        for reservation in expired_reservations:
            items = reservation.items
            if isinstance(items, list):
                for item in items:
                    product_id = item.get("product_id")
                    reserved_stock = item.get("reserved_stock", 0)
                    modifier_ids = item.get("modifier_ids", []) or []
                    if product_id and reserved_stock > 0:
                        await db.execute(
                            update(Product)
                            .where(
                                Product.id == UUID(str(product_id)),
                                Product.track_stock.is_(True),
                            )
                            .values(stock=Product.stock + reserved_stock)
                        )
                    for mod_id in modifier_ids:
                        mod_reserved = item.get(f"modifier_{mod_id}_reserved", 0)
                        if mod_reserved > 0:
                            await db.execute(
                                update(Modifier)
                                .where(
                                    Modifier.id == UUID(str(mod_id)),
                                    Modifier.track_stock.is_(True),
                                )
                                .values(stock=Modifier.stock + mod_reserved)
                            )
            reservation.status = "EXPIRED"
            order_stmt = select(Order).where(Order.id == reservation.order_id)
            order_res = await db.execute(order_stmt)
            order = order_res.scalar_one_or_none()
            if order is not None and order.status == OrderStatusEnum.PAYMENT_1_PENDING:
                order.status = OrderStatusEnum.CANCELLED
                order.cancellation_reason = "Reserva expirada sin reporte de pago"
                order.updated_at = now
            expired_count += 1
        await db.commit()
    return {"expired_count": expired_count, "timestamp": now.isoformat()}


@shared_task(name="app.tasks.reservations.expire_reservations")
def expire_reservations() -> dict:
    """Expira reservas ACTIVE vencidas y repone stock. Corre cada minuto."""
    return asyncio.run(_expire_reservations_async())


async def _cleanup_old_reservations_async() -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    async with get_db_context() as db:
        stmt = select(OrderReservation).where(
            OrderReservation.status.in_(["EXPIRED", "RELEASED", "CONSUMED"]),
            OrderReservation.reserved_at < cutoff,
        )
        result = await db.execute(stmt)
        old = list(result.scalars().all())
        for res in old:
            await db.delete(res)
        await db.commit()
        return {"deleted_count": len(old)}


@shared_task(name="app.tasks.reservations.cleanup_expired_reservations")
def cleanup_expired_reservations() -> dict:
    return asyncio.run(_cleanup_old_reservations_async())


def reservation_ttl() -> timedelta:
    return timedelta(minutes=settings.RESERVATION_TTL_MINUTES)
