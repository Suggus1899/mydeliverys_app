"""Reporte de pagos del cliente."""

from uuid import UUID

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import AppException, create_success_response
from app.models.order import Order
from app.schemas.orders_payments import PaymentReportRequest
from app.services import payments as payments_service

router = APIRouter()


@router.post("/{order_id}/report", status_code=201)
async def report_payment(
    order_id: UUID,
    body: PaymentReportRequest,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        raise AppException("ORDER_NOT_FOUND", "Pedido no encontrado.", 404)
    if body.phase != "FIRST_HALF":
        raise AppException("INVALID_PHASE", "Fase invalida para este endpoint.", 422)
    payment = await payments_service.report_first_payment(
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
        {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "order_status": order.status.value,
        },
        "Pago reportado. En verificacion.",
        201,
    )
