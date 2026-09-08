"""Pedidos: cotizacion draft, consulta, cancelacion."""

from uuid import UUID

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import desc, select

from app.api.deps import CurrentUser, DbSession, require_order_access
from app.core.exceptions import AppException, create_success_response
from app.models.order import Order
from app.schemas.common import OrderDraftRequest
from app.services import orders as orders_service

router = APIRouter()


def _serialize_order(o: Order) -> dict:
    return {
        "id": str(o.id),
        "order_number": o.order_number,
        "status": o.status.value,
        "subtotal_amount": str(o.subtotal_amount),
        "delivery_fee": str(o.delivery_fee),
        "platform_fee": str(o.platform_fee),
        "total_amount": str(o.total_amount),
        "payment_breakdown": {
            "total": str(o.total_amount),
            "first_half": str(o.first_half_amount),
            "second_half": str(o.second_half_amount),
            "total_ves": str(o.total_ves_amount),
            "first_half_ves": str(o.first_half_ves_amount),
            "second_half_ves": str(o.second_half_ves_amount),
        },
        "delivery_distance_m": str(o.delivery_distance_m),
        "quote_snapshot": o.quote_snapshot,
        "created_at": o.created_at.isoformat(),
        "quote_expires_at": o.quote_expires_at.isoformat(),
    }


@router.post("/draft", status_code=201)
async def create_draft(
    body: OrderDraftRequest,
    user: CurrentUser,
    db: DbSession,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> JSONResponse:
    if not x_idempotency_key:
        raise AppException("MISSING_IDEMPOTENCY_KEY", "Falta X-Idempotency-Key.", 400)
    items = [
        {
            "product_id": str(i.product_id),
            "quantity": i.quantity,
            "modifier_ids": [str(m.modifier_id) for m in i.modifiers],
        }
        for i in body.items
    ]
    order = await orders_service.create_draft(db, user, items, body.address_id)
    return create_success_response(_serialize_order(order), "Cotizacion creada.", 201)


@router.get("")
async def list_orders(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> JSONResponse:
    stmt = (
        select(Order)
        .where(Order.customer_id == user.id)
        .order_by(desc(Order.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return create_success_response([_serialize_order(o) for o in rows])


@router.get("/{order_id}")
async def get_order(order_id: UUID, user: CurrentUser, db: DbSession) -> JSONResponse:
    order = await orders_service.get_order_detail(db, order_id)
    await require_order_access(order, user, db)
    return create_success_response(_serialize_order(order))


@router.post("/{order_id}/cancel")
async def cancel_order(order_id: UUID, user: CurrentUser, db: DbSession) -> JSONResponse:
    order = await orders_service.get_order_detail(db, order_id)
    if order.customer_id != user.id:
        raise AppException("ORDER_NOT_OWNED", "No es tu pedido.", 403)
    order = await orders_service.cancel_draft(db, order, "Cancelado por cliente")
    return create_success_response(_serialize_order(order), "Pedido cancelado.")
