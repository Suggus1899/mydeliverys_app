"""Canales en tiempo real autenticados y recuperables por consulta REST."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.api.deps import require_order_access
from app.core.database import get_db_context
from app.core.security import decode_token
from app.infrastructure.redis import get_redis
from app.models.order import Order
from app.models.user import RestaurantStaff, RoleEnum, User, UserSession
from app.services.tracking import ephemeral_key, location_channel, publish_location

router = APIRouter()
logger = logging.getLogger(__name__)


def _auth_socket(token: str | None) -> tuple[UUID, RoleEnum, str, str] | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.type not in ("access", "web_session"):
            return None
        return UUID(payload.sub), RoleEnum(payload.role), payload.type, token
    except (ValueError, KeyError):
        return None


async def _active_user(auth: tuple[UUID, RoleEnum, str, str]) -> User | None:
    user_id, role, token_type, raw_token = auth
    async with get_db_context() as db:
        user = await db.scalar(
            select(User).where(User.id == user_id, User.role == role, User.is_active.is_(True))
        )
        if user is None or token_type != "web_session":
            return user
        session_id = await db.scalar(
            select(UserSession.id).where(
                UserSession.user_id == user_id,
                UserSession.refresh_token_hash == sha256(raw_token.encode()).hexdigest(),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > datetime.now(UTC),
            )
        )
        return user if session_id is not None else None


async def _forward_channel(websocket: WebSocket, channel: str) -> None:
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                raw = message.get("data")
                await websocket.send_text(raw if isinstance(raw, str) else str(raw))
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:
            logger.exception("No se pudo cerrar la suscripcion %s", channel)


@router.websocket("/ws/driver/track")
async def ws_driver_track(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    auth = _auth_socket(token or websocket.cookies.get("mds_session"))
    if auth is None or auth[1] != RoleEnum.DRIVER:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    driver = await _active_user(auth)
    if driver is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                order_id = UUID(str(data["order_id"]))
                latitude = Decimal(str(data["latitude"]))
                longitude = Decimal(str(data["longitude"]))
                if not Decimal("-90") <= latitude <= Decimal("90"):
                    raise ValueError("latitude")
                if not Decimal("-180") <= longitude <= Decimal("180"):
                    raise ValueError("longitude")
                async with get_db_context() as db:
                    result = await publish_location(
                        db,
                        driver,
                        order_id,
                        latitude,
                        longitude,
                        float(data["heading"]) if data.get("heading") is not None else None,
                        int(data["battery"]) if data.get("battery") is not None else None,
                    )
                await websocket.send_text(json.dumps({"success": True, "data": result}))
            except (KeyError, ValueError, TypeError, InvalidOperation):
                await websocket.send_text(
                    json.dumps(
                        {
                            "success": False,
                            "error_code": "INVALID_LOCATION",
                            "message": "Ubicacion invalida.",
                            "data": None,
                        }
                    )
                )
    except WebSocketDisconnect:
        return


@router.websocket("/ws/customer/track/{order_id}")
async def ws_customer_track(
    websocket: WebSocket, order_id: UUID, token: str | None = Query(default=None)
) -> None:
    auth = _auth_socket(token or websocket.cookies.get("mds_session"))
    if auth is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user = await _active_user(auth)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    async with get_db_context() as db:
        order = await db.scalar(select(Order).where(Order.id == order_id))
        if order is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        try:
            await require_order_access(order, user, db)
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    await websocket.accept()
    redis = get_redis()
    latest = await redis.get(ephemeral_key(order_id))
    if latest:
        await websocket.send_text(latest)
    forward_task = asyncio.create_task(_forward_channel(websocket, location_channel(order_id)))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
    finally:
        forward_task.cancel()
        await asyncio.gather(forward_task, return_exceptions=True)


@router.websocket("/ws/restaurant/orders")
async def ws_restaurant_orders(
    websocket: WebSocket, token: str | None = Query(default=None)
) -> None:
    auth = _auth_socket(token or websocket.cookies.get("mds_session"))
    if auth is None or auth[1] != RoleEnum.RESTAURANT_ADMIN:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user = await _active_user(auth)
    async with get_db_context() as db:
        restaurant_id = await db.scalar(
            select(RestaurantStaff.restaurant_id).where(
                RestaurantStaff.user_id == auth[0], RestaurantStaff.is_active.is_(True)
            )
        )
    if user is None or restaurant_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    try:
        await _forward_channel(websocket, f"restaurant:{restaurant_id}:orders")
    except (WebSocketDisconnect, asyncio.CancelledError):
        return


@router.websocket("/ws/admin/map")
async def ws_admin_map(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    auth = _auth_socket(token or websocket.cookies.get("mds_session"))
    if auth is None or auth[1] != RoleEnum.SUPER_ADMIN or await _active_user(auth) is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    try:
        await _forward_channel(websocket, "admin:map:updates")
    except (WebSocketDisconnect, asyncio.CancelledError):
        return
