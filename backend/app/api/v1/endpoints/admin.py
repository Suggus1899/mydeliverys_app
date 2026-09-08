"""Administracion: conciliacion pagos, socios, reasignacion, salud tasa."""

import logging
from uuid import UUID

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import desc, select

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import AppException, create_success_response
from app.models.order import Order
from app.models.payment import Payment, PaymentStatusEnum
from app.models.user import RoleEnum
from app.schemas.common import RestaurantCreate
from app.schemas.orders_payments import (
    AdminDiscrepancyRequest,
    AdminDriverCreate,
    AdminOrderReassignRequest,
    AdminRefundCreate,
    AdminRefundUpdate,
    AdminRestaurantStaffCreate,
    AdminSettlementCreate,
    AdminSettlementUpdate,
    PaymentRejectRequest,
)
from app.services import auth as auth_service
from app.services import catalog as catalog_service
from app.services import finance_ops
from app.services import payments as payments_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_admin(user: CurrentUser) -> None:
    if user.role != RoleEnum.SUPER_ADMIN:
        raise AppException("FORBIDDEN_ROLE", "Solo Super Admin.", 403)


@router.get("/payments/pending")
async def list_pending(user: CurrentUser, db: DbSession) -> JSONResponse:
    _require_admin(user)
    stmt = (
        select(Payment, Order)
        .join(Order, Order.id == Payment.order_id)
        .where(Payment.status == PaymentStatusEnum.PENDING)
        .order_by(desc(Payment.created_at))
        .limit(100)
    )
    rows = list((await db.execute(stmt)).all())
    data = [
        {
            "payment_id": str(p.id),
            "order_id": str(o.id),
            "order_number": o.order_number,
            "phase": p.phase.value,
            "method": p.method.value,
            "amount_usd": str(p.amount),
            "reference_number": p.reference_number,
            "origin_bank": p.origin_bank,
            "proof_image_url": p.proof_image_url,
            "created_at": p.created_at.isoformat(),
        }
        for p, o in rows
    ]
    return create_success_response(data)


@router.post("/payments/{payment_id}/verify")
async def verify_payment(
    payment_id: UUID,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    _require_admin(user)
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    payment = (
        await db.execute(select(Payment).where(Payment.id == payment_id))
    ).scalar_one_or_none()
    if payment is None:
        raise AppException("PAYMENT_NOT_FOUND", "Pago no encontrado.", 404)
    order = await payments_service.verify_payment(db, payment, user)
    return create_success_response(
        {"payment_id": str(payment.id), "order_status": order.status.value}, "Pago verificado."
    )


@router.post("/payments/{payment_id}/reject")
async def reject_payment(
    payment_id: UUID,
    body: PaymentRejectRequest,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    _require_admin(user)
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    payment = (
        await db.execute(select(Payment).where(Payment.id == payment_id))
    ).scalar_one_or_none()
    if payment is None:
        raise AppException("PAYMENT_NOT_FOUND", "Pago no encontrado.", 404)
    order = await payments_service.reject_payment(db, payment, user, body.reason)
    return create_success_response(
        {"payment_id": str(payment.id), "order_status": order.status.value}, "Pago rechazado."
    )


@router.post("/restaurants", status_code=201)
async def create_restaurant(
    body: RestaurantCreate, user: CurrentUser, db: DbSession
) -> JSONResponse:
    _require_admin(user)
    r = await catalog_service.create_restaurant(
        db,
        body.name,
        body.phone_number,
        body.address,
        body.latitude,
        body.longitude,
        body.commission_rate,
    )
    return create_success_response({"id": str(r.id)}, "Restaurante creado.", 201)


@router.post("/restaurant-staff", status_code=201)
async def create_staff(
    body: AdminRestaurantStaffCreate, user: CurrentUser, db: DbSession
) -> JSONResponse:
    _require_admin(user)
    created = await auth_service.create_restaurant_staff(
        db, body.restaurant_id, body.phone, body.full_name, body.temp_password
    )
    return create_success_response(
        {"id": str(created.id)}, "Operador creado. Debe cambiar clave.", 201
    )


@router.post("/drivers", status_code=201)
async def create_driver(body: AdminDriverCreate, user: CurrentUser, db: DbSession) -> JSONResponse:
    _require_admin(user)
    created = await auth_service.create_driver(db, body.phone, body.full_name, body.temp_password)
    return create_success_response({"id": str(created.id)}, "Conductor creado.", 201)


@router.post("/orders/{order_id}/reassign")
async def reassign_order(
    order_id: UUID,
    body: AdminOrderReassignRequest,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    _require_admin(user)
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    from sqlalchemy import update

    from app.models.order import OrderStatusEnum

    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        raise AppException("ORDER_NOT_FOUND", "No encontrado.", 404)
    if order.status not in (OrderStatusEnum.READY_FOR_PICKUP, OrderStatusEnum.ON_THE_WAY):
        raise AppException("INVALID_ORDER_STATUS", "No reasignable en este estado.", 409)
    if order.status == OrderStatusEnum.ON_THE_WAY and not body.evidence_image_url:
        raise AppException("CUSTODY_EVIDENCE_REQUIRED", "Evidencia de custodia requerida.", 400)
    old_driver = order.driver_id
    stmt = (
        update(Order)
        .where(Order.id == order_id, Order.driver_id == old_driver)
        .values(driver_id=body.new_driver_id)
    )
    await db.execute(stmt)
    from uuid import uuid4

    from app.models.audit import AuditLog

    db.add(
        AuditLog(
            id=uuid4(),
            admin_user_id=user.id,
            action="REASSIGN_ORDER",
            entity_name="orders",
            entity_id=order.id,
            details={"old_driver": str(old_driver), "new_driver": str(body.new_driver_id)},
            ip_address=None,
        )
    )
    await db.commit()
    try:
        from app.tasks.notifications import notify_driver_reassigned

        notify_driver_reassigned.delay(str(old_driver), str(order_id), "Reasignado por admin")
    except Exception:
        logger.exception("No se pudo notificar la reasignacion")
    return create_success_response(
        {"id": str(order_id), "new_driver": str(body.new_driver_id)}, "Orden reasignada."
    )


@router.post("/refunds", status_code=201)
async def create_refund(body: AdminRefundCreate, user: CurrentUser, db: DbSession) -> JSONResponse:
    _require_admin(user)
    refund = await finance_ops.create_refund(
        db,
        user,
        body.order_id,
        body.payment_id,
        body.type,
        body.reason,
        body.amount_usd,
        body.proof_image_url,
    )
    return create_success_response(
        {"id": str(refund.id), "status": refund.status.value}, "Reembolso creado.", 201
    )


@router.post("/refunds/{refund_id}/approve")
async def approve_refund(
    refund_id: UUID, body: AdminRefundUpdate, user: CurrentUser, db: DbSession
) -> JSONResponse:
    _require_admin(user)
    refund = await finance_ops.approve_refund(db, user, refund_id, body.status == "APPROVED")
    return create_success_response({"id": str(refund.id), "status": refund.status.value})


@router.post("/settlements", status_code=201)
async def create_settlement(
    body: AdminSettlementCreate, user: CurrentUser, db: DbSession
) -> JSONResponse:
    _require_admin(user)
    from datetime import date

    settlement = await finance_ops.create_settlement(
        db,
        user,
        body.entity_type,
        body.entity_id,
        date.fromisoformat(body.period_start),
        date.fromisoformat(body.period_end),
        body.currency,
    )
    return create_success_response(
        {"id": str(settlement.id), "net": str(settlement.net_amount)}, "Liquidacion creada.", 201
    )


@router.post("/settlements/{settlement_id}/confirm")
async def confirm_settlement(
    settlement_id: UUID, body: AdminSettlementUpdate, user: CurrentUser, db: DbSession
) -> JSONResponse:
    _require_admin(user)
    if body.status == "CONFIRMED" and await settlement_net_negative(db, settlement_id):
        pass  # la nota se valida en servicio/operacion manual
    s = await finance_ops.confirm_settlement(
        db, user, settlement_id, body.status, body.proof_image_url
    )
    return create_success_response({"id": str(s.id), "status": s.status.value})


@router.post("/payments/{payment_id}/flag-discrepancy")
async def flag_discrepancy(
    payment_id: UUID, body: AdminDiscrepancyRequest, user: CurrentUser, db: DbSession
) -> JSONResponse:
    _require_admin(user)
    payment = await finance_ops.flag_discrepancy(db, user, payment_id, body.reported_amount)
    return create_success_response(
        {
            "id": str(payment.id),
            "reconciliation": payment.reconciliation_status.value,
            "diff": str(payment.discrepancy_amount),
        }
    )


@router.get("/incidents")
async def list_incidents(
    user: CurrentUser,
    db: DbSession,
    type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> JSONResponse:
    """Bandeja de incidencias: reembolsos pendientes, fallos de entrega y pagos rechazados."""
    from app.models.order import OrderStatusEnum

    _require_admin(user)
    wanted = {"CANCELLED_WITH_REFUND", "DELIVERY_FAILED"}
    if type is not None:
        if type not in wanted:
            raise AppException(
                "INVALID_TYPE", "type debe ser CANCELLED_WITH_REFUND o DELIVERY_FAILED.", 422
            )
        wanted = {type}
    stmt = (
        select(Order)
        .where(Order.status.in_([OrderStatusEnum(s) for s in wanted]))  # type: ignore[arg-type]
        .order_by(desc(Order.created_at))
        .limit(limit)
    )
    orders = list((await db.execute(stmt)).scalars().all())
    rejected = list(
        (
            await db.execute(
                select(Payment)
                .where(Payment.status == PaymentStatusEnum.REJECTED)
                .order_by(desc(Payment.created_at))
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return create_success_response(
        {
            "orders": [
                {
                    "id": str(o.id),
                    "order_number": o.order_number,
                    "status": o.status.value,
                    "reason": o.cancellation_reason,
                }
                for o in orders
            ],
            "rejected_payments": [
                {"id": str(p.id), "order_id": str(p.order_id), "phase": p.phase.value}
                for p in rejected
            ],
        }
    )


async def settlement_net_negative(db: DbSession, settlement_id: UUID) -> bool:
    from sqlalchemy import select as _select

    from app.models.financial import Settlement

    s = (
        await db.execute(_select(Settlement).where(Settlement.id == settlement_id))
    ).scalar_one_or_none()
    return bool(s is not None and s.net_amount < 0)


@router.get("/exchange-rate/health")
async def exchange_health(user: CurrentUser, db: DbSession) -> JSONResponse:
    _require_admin(user)
    from datetime import UTC, datetime

    from app.core.config import settings
    from app.models.financial import ExchangeRate

    stmt = (
        select(ExchangeRate)
        .where(ExchangeRate.is_valid.is_(True))
        .order_by(desc(ExchangeRate.queried_at))
        .limit(1)
    )
    last = (await db.execute(stmt)).scalar_one_or_none()
    if last is None:
        return create_success_response({"status": "critical", "is_blocking_new_orders": True})
    hours = (datetime.now(UTC) - last.queried_at).total_seconds() / 3600
    return create_success_response(
        {
            "last_valid_rate": str(last.rate),
            "last_valid_queried_at": last.queried_at.isoformat(),
            "seconds_since_last_valid": int(hours * 3600),
            "is_blocking_new_orders": hours > settings.EXCHANGE_RATE_STALE_HOURS,
        }
    )
