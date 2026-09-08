import enum
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.restaurant import Modifier, Product, Restaurant
    from app.models.tracking import DeliveryTracking, GeofenceEvent
    from app.models.user import User, UserAddress


class OrderStatusEnum(str, enum.Enum):
    PAYMENT_1_PENDING = "PAYMENT_1_PENDING"
    PAYMENT_1_VERIFYING = "PAYMENT_1_VERIFYING"
    PREPARING = "PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    ON_THE_WAY = "ON_THE_WAY"
    ARRIVED_AT_CUSTOMER = "ARRIVED_AT_CUSTOMER"
    PAYMENT_2_VERIFYING = "PAYMENT_2_VERIFYING"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    CANCELLED_WITH_REFUND = "CANCELLED_WITH_REFUND"
    DELIVERY_FAILED = "DELIVERY_FAILED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    delivery_address_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_addresses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[OrderStatusEnum] = mapped_column(
        Enum(OrderStatusEnum), nullable=False, default=OrderStatusEnum.PAYMENT_1_PENDING, index=True
    )

    # Financial snapshot (immutable after creation)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    first_half_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    second_half_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_ves_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    first_half_ves_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    second_half_ves_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    delivery_distance_m: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Exchange rate snapshot
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    exchange_rate_source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="dolarapi_oficial"
    )
    exchange_rate_effective_date: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # YYYY-MM-DD
    exchange_rate_queried_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    quote_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Quote snapshot (complete immutable copy of quote data)
    quote_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Operational fields
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Kitchen acknowledgment
    arrived_at_restaurant_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    arrived_at_customer_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    customer: Mapped["User"] = relationship(
        back_populates="orders_as_customer", foreign_keys=[customer_id]
    )
    restaurant: Mapped["Restaurant"] = relationship(back_populates="orders")
    driver: Mapped[Optional["User"]] = relationship(
        back_populates="orders_as_driver", foreign_keys=[driver_id]
    )
    delivery_address: Mapped["UserAddress"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    tracking: Mapped[list["DeliveryTracking"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    reservation: Mapped[Optional["OrderReservation"]] = relationship(
        back_populates="order", uselist=False
    )
    geofence_events: Mapped[list["GeofenceEvent"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_orders_customer_id_status", "customer_id", "status"),
        Index("ix_orders_restaurant_id_status", "restaurant_id", "status"),
        Index("ix_orders_driver_id_status", "driver_id", "status"),
        Index("ix_orders_status_created_at", "status", "created_at"),
        Index(
            "uq_orders_driver_active",
            "driver_id",
            unique=True,
            postgresql_where=text(
                "driver_id IS NOT NULL AND status IN "
                "('READY_FOR_PICKUP','ON_THE_WAY','ARRIVED_AT_CUSTOMER','PAYMENT_2_VERIFYING')"
            ),
        ),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )  # base_price + modifiers at time of order
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    product_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )  # name, description, base_price, image_url

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()
    modifiers: Mapped[list["OrderModifier"]] = relationship(
        back_populates="order_item", cascade="all, delete-orphan"
    )


class OrderModifier(Base):
    __tablename__ = "order_modifiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    modifier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modifiers.id", ondelete="RESTRICT"), nullable=False
    )
    modifier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    extra_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order_item: Mapped["OrderItem"] = relationship(back_populates="modifiers")
    modifier: Mapped["Modifier"] = relationship()


class OrderReservation(Base):
    __tablename__ = "order_reservations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE"
    )  # ACTIVE, UNDER_REVIEW, CONSUMED, EXPIRED, RELEASED
    items: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False
    )  # [{product_id, modifier_ids[], quantity, reserved_stock}]

    order: Mapped["Order"] = relationship(back_populates="reservation")

    __table_args__ = (Index("ix_order_reservations_status_expires_at", "status", "expires_at"),)
