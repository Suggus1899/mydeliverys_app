"""Tracking REST: ping actual, lote historico, historial."""

from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_order_access
from app.core.exceptions import AppException, create_success_response
from app.models.order import Order
from app.models.user import RoleEnum
from app.schemas.orders_payments import DriverLocationUpdate, LocationHistoryBatch
from app.services import tracking as tracking_service

router = APIRouter()


@router.post("/location")
async def post_location(
    body: DriverLocationUpdate, user: CurrentUser, db: DbSession
) -> JSONResponse:
    if user.role != RoleEnum.DRIVER:
        raise AppException("FORBIDDEN_ROLE", "Solo conductores.", 403)
    data = await tracking_service.publish_location(
        db, user, body.order_id, body.latitude, body.longitude, body.heading, body.battery_level
    )
    return create_success_response(data, "Ubicacion recibida.")


@router.post("/location-batch")
async def post_location_batch(
    body: LocationHistoryBatch, user: CurrentUser, db: DbSession
) -> JSONResponse:
    if user.role != RoleEnum.DRIVER:
        raise AppException("FORBIDDEN_ROLE", "Solo conductores.", 403)
    points = [
        {
            "latitude": str(p.latitude),
            "longitude": str(p.longitude),
            "battery_level": p.battery_level,
        }
        for p in body.points
    ]
    data = await tracking_service.persist_batch(db, user, body.order_id, points)
    return create_success_response(data, "Lote recibido.")


@router.get("/order/{order_id}")
async def get_tracking(order_id: UUID, user: CurrentUser, db: DbSession) -> JSONResponse:
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        raise AppException("ORDER_NOT_FOUND", "Pedido no encontrado.", 404)
    await require_order_access(order, user, db)
    data = await tracking_service.get_history(db, order_id)
    return create_success_response(data)
