"""Operacion cocina: Kanban 3 columnas + historial, reconocimiento, listo."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from sqlalchemy import desc, select

from app.api.deps import CurrentUser, DbSession, require_restaurant_ownership
from app.core.exceptions import AppException, create_success_response
from app.domain.states import OrderStatus, transition
from app.models.order import Order, OrderStatusEnum
from app.models.user import RoleEnum
from app.services.events import record_order_event

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/kanban")
async def kanban(
    restaurant_id: UUID,
    user: CurrentUser,
    db: DbSession,
    acknowledged: bool | None = Query(default=None),
) -> JSONResponse:
    await require_restaurant_ownership(restaurant_id, user, db)
    stmt = (
        select(Order)
        .where(Order.restaurant_id == restaurant_id, Order.status == OrderStatusEnum.PREPARING)
        .order_by(desc(Order.created_at))
        .limit(100)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    nuevos = [o for o in rows if o.acknowledged_at is None]
    en_prep = [o for o in rows if o.acknowledged_at is not None]

    def _ser(o: Order) -> dict:
        mins = None
        if o.acknowledged_at:
            mins = int((datetime.now(UTC) - o.acknowledged_at).total_seconds() // 60)
        return {
            "id": str(o.id),
            "order_number": o.order_number,
            "created_at": o.created_at.isoformat(),
            "acknowledged_at": o.acknowledged_at.isoformat() if o.acknowledged_at else None,
            "minutes_in_prep": mins,
            "total": str(o.total_amount),
        }

    if acknowledged is True:
        return create_success_response([_ser(o) for o in en_prep])
    if acknowledged is False:
        return create_success_response([_ser(o) for o in nuevos])
    return create_success_response(
        {"nuevos": [_ser(o) for o in nuevos], "en_preparacion": [_ser(o) for o in en_prep]}
    )


@router.get("/ready-list")
async def ready_list(restaurant_id: UUID, user: CurrentUser, db: DbSession) -> JSONResponse:
    await require_restaurant_ownership(restaurant_id, user, db)
    stmt = (
        select(Order)
        .where(
            Order.restaurant_id == restaurant_id, Order.status == OrderStatusEnum.READY_FOR_PICKUP
        )
        .order_by(desc(Order.created_at))
        .limit(100)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return create_success_response(
        [{"id": str(o.id), "order_number": o.order_number} for o in rows]
    )


@router.get("/history")
async def history(
    restaurant_id: UUID,
    user: CurrentUser,
    db: DbSession,
    status: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> JSONResponse:
    from datetime import date

    await require_restaurant_ownership(restaurant_id, user, db)
    terminal = [
        OrderStatusEnum.DELIVERED,
        OrderStatusEnum.CANCELLED,
        OrderStatusEnum.CANCELLED_WITH_REFUND,
        OrderStatusEnum.DELIVERY_FAILED,
    ]
    stmt = (
        select(Order)
        .where(Order.restaurant_id == restaurant_id, Order.status.in_(terminal))  # type: ignore[arg-type]
        .order_by(desc(Order.created_at))
        .limit(limit)
    )
    if status is not None:
        try:
            wanted = OrderStatusEnum(status)
        except ValueError as err:
            raise AppException("INVALID_STATUS", "Estado invalido.", 422) from err
        if wanted not in terminal:
            raise AppException("INVALID_STATUS", "Solo estados terminales.", 422)
        stmt = stmt.where(Order.status == wanted)
    if since is not None:
        try:
            day = date.fromisoformat(since)
        except ValueError as err:
            raise AppException("INVALID_DATE", "since debe ser YYYY-MM-DD.", 422) from err
        stmt = stmt.where(Order.created_at >= datetime(day.year, day.month, day.day, tzinfo=UTC))
    if until is not None:
        try:
            day = date.fromisoformat(until)
        except ValueError as err:
            raise AppException("INVALID_DATE", "until debe ser YYYY-MM-DD.", 422) from err
        stmt = stmt.where(Order.created_at < datetime(day.year, day.month, day.day, tzinfo=UTC))
    rows = list((await db.execute(stmt)).scalars().all())
    return create_success_response(
        [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "status": o.status.value,
                "total": str(o.total_amount),
                "created_at": o.created_at.isoformat(),
            }
            for o in rows
        ]
    )


@router.post("/orders/{order_id}/acknowledge")
async def acknowledge(order_id: UUID, user: CurrentUser, db: DbSession) -> JSONResponse:
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        from app.core.exceptions import AppException

        raise AppException("ORDER_NOT_FOUND", "No encontrado.", 404)
    await require_restaurant_ownership(order.restaurant_id, user, db)
    if order.status != OrderStatusEnum.PREPARING:
        from app.core.exceptions import AppException

        raise AppException("INVALID_ORDER_STATUS", "Solo en PREPARING.", 409)
    if user.role != RoleEnum.RESTAURANT_ADMIN and user.role != RoleEnum.SUPER_ADMIN:
        from app.core.exceptions import AppException

        raise AppException("FORBIDDEN_ROLE", "Solo cocina.", 403)
    order.acknowledged_at = datetime.now(UTC)
    record_order_event(db, order, "ORDER_ACKNOWLEDGED")
    await db.commit()
    return create_success_response(
        {"id": str(order.id), "acknowledged_at": order.acknowledged_at.isoformat()}
    )


@router.post("/orders/{order_id}/ready")
async def mark_ready(order_id: UUID, user: CurrentUser, db: DbSession) -> JSONResponse:
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        from app.core.exceptions import AppException

        raise AppException("ORDER_NOT_FOUND", "No encontrado.", 404)
    await require_restaurant_ownership(order.restaurant_id, user, db)
    transition(OrderStatus(order.status.value), OrderStatus.READY_FOR_PICKUP)
    order.status = OrderStatusEnum.READY_FOR_PICKUP
    record_order_event(db, order, "ORDER_READY_FOR_PICKUP")
    await db.commit()
    try:
        from app.infrastructure.redis import get_redis

        redis = get_redis()
        await redis.publish(
            f"restaurant:{order.restaurant_id}:orders", f"READY {order.order_number}"
        )
    except Exception:
        logger.exception("No se pudo publicar que el pedido esta listo")
    return create_success_response(
        {"id": str(order.id), "status": order.status.value}, "Lista para recoger."
    )
