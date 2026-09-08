"""Repartidor: disponibilidad, aceptacion atomica, recogida, llegada, cobro."""

import logging
from uuid import UUID

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import AppException, create_success_response
from app.domain.states import OrderStatus, transition
from app.models.order import Order, OrderStatusEnum
from app.models.user import RoleEnum
from app.schemas.orders_payments import (
    DriverCollectCashRequest,
    DriverConfirmDigitalRequest,
    DriverOrderArriveCustomerRequest,
    DriverReportAbsentRequest,
    DriverReportIncidentRequest,
)
from app.services import payments as payments_service
from app.services.events import record_order_event

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_driver(user: CurrentUser) -> None:
    if user.role != RoleEnum.DRIVER:
        raise AppException("FORBIDDEN_ROLE", "Solo conductores.", 403)


@router.patch("/availability")
async def set_availability(
    user: CurrentUser, db: DbSession, is_available: bool = True
) -> JSONResponse:
    _require_driver(user)
    # V1: persistimos en Redis `driver:available:{id}`
    try:
        from app.infrastructure.redis import get_redis

        redis = get_redis()
        await redis.set(f"driver:available:{user.id}", "1" if is_available else "0", ex=86400)
    except Exception as exc:
        raise AppException(
            "REDIS_UNAVAILABLE", "No se pudo actualizar la disponibilidad.", 503
        ) from exc
    return create_success_response({"driver_id": str(user.id), "is_available": is_available})


@router.get("/orders/available")
async def list_available(user: CurrentUser, db: DbSession) -> JSONResponse:
    _require_driver(user)
    stmt = (
        select(Order)
        .where(Order.status == OrderStatusEnum.READY_FOR_PICKUP, Order.driver_id.is_(None))
        .limit(20)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return create_success_response(
        [{"id": str(o.id), "order_number": o.order_number} for o in rows]
    )


@router.post("/orders/{order_id}/accept")
async def accept_order(
    order_id: UUID,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    _require_driver(user)
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    # Asignacion atomica: WHERE driver_id IS NULL AND status READY_FOR_PICKUP
    stmt = (
        update(Order)
        .where(
            Order.id == order_id,
            Order.driver_id.is_(None),
            Order.status == OrderStatusEnum.READY_FOR_PICKUP,
        )
        .values(driver_id=user.id)
        .returning(Order)
    )
    result = await db.execute(stmt)
    assigned_order = result.scalar_one_or_none()
    if assigned_order is None:
        raise AppException(
            "ORDER_ALREADY_ASSIGNED", "Este pedido ya fue tomado por otro conductor.", 409
        )
    record_order_event(db, assigned_order, "DRIVER_ASSIGNED")
    await db.commit()
    return create_success_response(
        {"id": str(order_id), "status": "READY_FOR_PICKUP"}, "Pedido asignado."
    )


async def _get_assigned(order_id: UUID, user: CurrentUser, db: DbSession) -> Order:
    _require_driver(user)
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        raise AppException("ORDER_NOT_FOUND", "No encontrado.", 404)
    if order.driver_id != user.id:
        raise AppException("NOT_ASSIGNED_DRIVER", "No asignado a ti.", 403)
    return order


@router.post("/orders/{order_id}/pickup")
async def pickup_order(
    order_id: UUID,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    order = await _get_assigned(order_id, user, db)
    # La aceptacion solo asigna; la recogida inicia la ruta.
    if order.status == OrderStatusEnum.READY_FOR_PICKUP:
        transition(OrderStatus(order.status.value), OrderStatus.ON_THE_WAY)
        order.status = OrderStatusEnum.ON_THE_WAY
        record_order_event(db, order, "ORDER_PICKED_UP")
        await db.commit()
    return create_success_response({"id": str(order_id), "status": order.status.value})


@router.post("/orders/{order_id}/complete-delivery")
async def complete_delivery(
    order_id: UUID,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    order = await _get_assigned(order_id, user, db)
    await payments_service.driver_complete_delivery(db, order, user)
    return create_success_response(
        {"id": str(order.id), "status": order.status.value}, "Entrega confirmada."
    )


@router.post("/orders/{order_id}/arrived")
async def arrived_customer(
    order_id: UUID,
    body: DriverOrderArriveCustomerRequest,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    order = await _get_assigned(order_id, user, db)
    if order.status == OrderStatusEnum.ON_THE_WAY:
        from datetime import UTC, datetime

        transition(OrderStatus(order.status.value), OrderStatus.ARRIVED_AT_CUSTOMER)
        order.status = OrderStatusEnum.ARRIVED_AT_CUSTOMER
        order.arrived_at_customer_at = datetime.now(UTC)
        record_order_event(db, order, "DRIVER_ARRIVED_CUSTOMER")
        # Geofence audit
        from app.models.tracking import GeofenceEvent

        db.add(
            GeofenceEvent(
                order_id=order.id,
                driver_id=user.id,
                event_type="CUSTOMER_ARRIVAL",
                triggered_by="MANUAL_DRIVER" if body.manual else "AUTO_GPS",
            )
        )
        await db.commit()
    return create_success_response({"id": str(order_id), "status": order.status.value})


@router.post("/orders/{order_id}/collect-cash")
async def collect_cash(
    order_id: UUID,
    body: DriverCollectCashRequest,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    order = await _get_assigned(order_id, user, db)
    payment = await payments_service.driver_collect_cash(
        db, order, user, body.amount_usd, body.amount_ves, x_idempotency_key
    )
    return create_success_response(
        {"payment_id": str(payment.id), "order_status": order.status.value}, "Entrega finalizada."
    )


@router.post("/orders/{order_id}/confirm-digital")
async def confirm_digital(
    order_id: UUID,
    body: DriverConfirmDigitalRequest,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    order = await _get_assigned(order_id, user, db)
    payment = await payments_service.driver_report_digital(
        db,
        order,
        user,
        body.method,
        body.reference_number,
        body.origin_bank,
        body.proof_image_url,
        x_idempotency_key,
    )
    return create_success_response(
        {"payment_id": str(payment.id), "order_status": order.status.value}, "Pago en verificacion."
    )


@router.get("/earnings")
async def earnings(user: CurrentUser, db: DbSession) -> JSONResponse:
    _require_driver(user)
    from sqlalchemy import func

    from app.models.payment import Payment, PaymentPhaseEnum, PaymentStatusEnum

    total = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.verified_by == user.id,
            Payment.phase == PaymentPhaseEnum.SECOND_HALF,
            Payment.status == PaymentStatusEnum.VERIFIED,
        )
    )
    count = await db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.driver_id == user.id, Order.status == OrderStatusEnum.DELIVERED)
    )
    return create_success_response({"orders_completed": count or 0, "net_amount": str(total or 0)})


@router.post("/orders/{order_id}/report-absent")
async def report_absent(
    order_id: UUID,
    body: DriverReportAbsentRequest,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    """Cliente ausente: 15 min documentados desde llegada. Conserva primer 50%."""
    from datetime import UTC, datetime

    from app.models.payment import Payment, PaymentPhaseEnum, PaymentStatusEnum

    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    order = await _get_assigned(order_id, user, db)
    if order.status != OrderStatusEnum.ARRIVED_AT_CUSTOMER:
        raise AppException("INVALID_ORDER_STATUS", "Solo en destino.", 409)
    if order.arrived_at_customer_at is None:
        raise AppException("INVALID_ORDER_STATUS", "Sin marca de llegada.", 409)
    waited = (datetime.now(UTC) - order.arrived_at_customer_at).total_seconds() / 60
    if waited < 15:
        raise AppException(
            "WAIT_NOT_ELAPSED", f"Espera 15 min documentados (van {int(waited)}).", 409
        )
    pending_second = await db.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.order_id == order.id,
            Payment.phase == PaymentPhaseEnum.SECOND_HALF,
            Payment.status == PaymentStatusEnum.PENDING,
        )
    )
    if pending_second:
        raise AppException(
            "SECOND_PAYMENT_PENDING", "Hay un segundo pago en revision. No se puede cerrar.", 409
        )
    transition(OrderStatus(order.status.value), OrderStatus.DELIVERY_FAILED)
    order.status = OrderStatusEnum.DELIVERY_FAILED
    record_order_event(db, order, "DELIVERY_FAILED_CUSTOMER_ABSENT")
    order.cancellation_reason = (
        f"Cliente ausente 15min. Evidencia: {body.evidence_image_url}. Notas: {body.notes or '-'}"
    )
    await db.commit()
    return create_success_response(
        {"id": str(order_id), "status": order.status.value}, "Cierre por ausencia registrado."
    )


@router.post("/orders/{order_id}/report-incident")
async def report_incident(
    order_id: UUID,
    body: DriverReportIncidentRequest,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    """Accidente/averia en ruta: pasa a CANCELLED_WITH_REFUND y alerta a admin."""
    from uuid import uuid4

    from app.models.audit import AuditLog

    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    order = await _get_assigned(order_id, user, db)
    if order.status not in (OrderStatusEnum.READY_FOR_PICKUP, OrderStatusEnum.ON_THE_WAY):
        raise AppException("INVALID_ORDER_STATUS", "Incidencia solo antes de llegar.", 409)
    transition(OrderStatus(order.status.value), OrderStatus.CANCELLED_WITH_REFUND)
    order.status = OrderStatusEnum.CANCELLED_WITH_REFUND
    record_order_event(db, order, "DRIVER_INCIDENT")
    order.cancellation_reason = f"Incidencia driver {body.type}. Evidencia: {body.evidence_image_url or '-'}. Notas: {body.notes or '-'}"
    db.add(
        AuditLog(
            id=uuid4(),
            admin_user_id=user.id,
            action="DRIVER_INCIDENT",
            entity_name="orders",
            entity_id=order.id,
            details={"type": body.type, "evidence": body.evidence_image_url, "notes": body.notes},
            ip_address=None,
        )
    )
    await db.commit()
    try:
        from app.tasks.notifications import notify_admin_payment_pending

        notify_admin_payment_pending.delay(str(order.id), "INCIDENT")
    except Exception:
        logger.exception("No se pudo encolar la alerta de incidencia")
    return create_success_response(
        {"id": str(order_id), "status": order.status.value},
        "Incidencia reportada. Admin notificado.",
    )
