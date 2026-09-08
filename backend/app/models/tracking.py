import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class DeliveryTracking(Base):
    __tablename__ = "delivery_tracking"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location: Mapped[str] = mapped_column(Text, nullable=False)  # WKT format for PostGIS Point
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    is_historical: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )  # True for batch historical inserts

    order: Mapped["Order"] = relationship(back_populates="tracking")
    driver: Mapped["User"] = relationship()

    __table_args__ = (
        Index("ix_delivery_tracking_order_id_recorded_at", "order_id", "recorded_at"),
    )


class DriverLocationEphemeral:
    """Redis-backed ephemeral location - not persisted in PostgreSQL.
    This class documents the structure stored in Redis:
    Key: driver:location:{order_id}
    Value: {lat, lng, heading, battery, updated_at}
    TTL: 10 minutes
    """

    def __init__(self, lat: float = 0.0, lng: float = 0.0) -> None:
        self.lat = lat
        self.lng = lng


class GeofenceEvent(Base):
    __tablename__ = "geofence_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # RESTAURANT_APPROACH, CUSTOMER_ARRIVAL
    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False)  # AUTO_GPS, MANUAL_DRIVER
    distance_m: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    accuracy_m: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    order: Mapped["Order"] = relationship(back_populates="geofence_events")

    __table_args__ = (Index("ix_geofence_events_order_id_created_at", "order_id", "created_at"),)
