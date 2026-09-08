"""Seguimiento: ubicacion efimera Redis TTL 10min + historial cada 3min/hito.

RF-TRK-01..12. Puntos historicos nunca disparan geocercas.
"""

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.infrastructure.redis import get_redis
from app.models.order import Order, OrderStatusEnum
from app.models.tracking import DeliveryTracking, GeofenceEvent
from app.models.user import User

EPHEMERAL_TTL = 600  # 10 min
HISTORY_INTERVAL_S = 180  # 3 min
GEOFENCE_RADIUS_M = 100
MIN_ACCURACY_M = 50
logger = logging.getLogger(__name__)


def ephemeral_key(order_id: UUID | str) -> str:
    return f"driver:location:{order_id}"


def location_channel(order_id: UUID | str) -> str:
    return f"order:{order_id}:location"


async def publish_location(
    db: AsyncSession,
    driver: User,
    order_id: UUID,
    lat: Decimal,
    lon: Decimal,
    heading: float | None,
    battery: int | None,
) -> dict:
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        raise AppException("ORDER_NOT_FOUND", "Pedido no encontrado.", 404)
    if order.driver_id != driver.id:
        raise AppException("NOT_ASSIGNED_DRIVER", "No asignado.", 403)
    if order.status not in (
        OrderStatusEnum.ON_THE_WAY,
        OrderStatusEnum.ARRIVED_AT_CUSTOMER,
        OrderStatusEnum.READY_FOR_PICKUP,
    ):
        raise AppException("INVALID_ORDER_STATUS", "Sin tracking en este estado.", 409)

    now = datetime.now(UTC)
    payload = {
        "lat": str(lat),
        "lng": str(lon),
        "heading": heading,
        "battery": battery,
        "updated_at": now.isoformat(),
        "driver_id": str(driver.id),
    }
    realtime_published = True
    try:
        redis = get_redis()
        await redis.setex(ephemeral_key(order_id), EPHEMERAL_TTL, json.dumps(payload))
        await redis.publish(location_channel(order_id), json.dumps(payload))
        await redis.publish("admin:map:updates", json.dumps({"order_id": str(order_id), **payload}))
    except Exception:
        realtime_published = False
        logger.exception("No se pudo publicar la ubicacion en tiempo real")

    # Persistencia: cada 3 min o hito. Aqui: si ultimo > 3min, persiste.
    last = await db.scalar(
        select(DeliveryTracking.recorded_at)
        .where(DeliveryTracking.order_id == order_id)
        .order_by(desc(DeliveryTracking.recorded_at))
        .limit(1)
    )
    should_persist = last is None or (now - last).total_seconds() >= HISTORY_INTERVAL_S
    if should_persist:
        db.add(
            DeliveryTracking(
                order_id=order_id,
                driver_id=driver.id,
                location=f"POINT({lon} {lat})",
                battery_level=battery,
                recorded_at=now,
                is_historical=False,
            )
        )
        await db.commit()
    return {"persisted": should_persist, "realtime_published": realtime_published}


async def persist_batch(
    db: AsyncSession,
    driver: User,
    order_id: UUID,
    points: list[dict],
) -> dict:
    """Lote historico tras reconexion (max 50). is_historical=True, sin geocercas."""
    if len(points) > 50:
        raise AppException("BATCH_TOO_LARGE", "Maximo 50 puntos.", 422)
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order is None or order.driver_id != driver.id:
        raise AppException("NOT_ASSIGNED_DRIVER", "No asignado.", 403)
    for p in points[:50]:
        db.add(
            DeliveryTracking(
                order_id=order_id,
                driver_id=driver.id,
                location=f"POINT({p['longitude']} {p['latitude']})",
                battery_level=p.get("battery_level"),
                recorded_at=datetime.now(UTC),
                is_historical=True,
            )
        )
    await db.commit()
    return {"stored": min(len(points), 50)}


async def get_history(db: AsyncSession, order_id: UUID, limit: int = 100) -> list[dict]:
    stmt = (
        select(DeliveryTracking)
        .where(DeliveryTracking.order_id == order_id)
        .order_by(desc(DeliveryTracking.recorded_at))
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "location": r.location,
            "battery": r.battery_level,
            "at": r.recorded_at.isoformat(),
            "historical": r.is_historical,
        }
        for r in rows
    ]


async def record_geofence(
    db: AsyncSession,
    order_id: UUID,
    driver_id: UUID,
    event_type: str,
    triggered_by: str,
    distance_m: Decimal | None = None,
    accuracy_m: Decimal | None = None,
) -> None:
    db.add(
        GeofenceEvent(
            order_id=order_id,
            driver_id=driver_id,
            event_type=event_type,
            triggered_by=triggered_by,
            distance_m=distance_m,
            accuracy_m=accuracy_m,
        )
    )
