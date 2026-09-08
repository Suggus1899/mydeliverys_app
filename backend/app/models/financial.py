import enum
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="dolarapi_oficial")
    reported_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    queried_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    validation_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_exchange_rates_valid_effective", "is_valid", "effective_date"),
        Index("ix_exchange_rates_queried_at", "queried_at"),
    )


class DeliveryFeeTier(Base):
    __tablename__ = "delivery_fee_tiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    min_distance_m: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), nullable=False
    )
    max_distance_m: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fee_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        # Constraint: no overlapping active tiers (enforced at application level)
        # Upper bound inclusive: distance <= max_distance_m
        UniqueConstraint("name", name="uq_delivery_fee_tier_name"),
    )


class PlatformFeeConfig(Base):
    __tablename__ = "platform_fee_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fee_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        # Only one active config at a time
        Index(
            "ix_platform_fee_config_active",
            "is_active",
            unique=True,
            postgresql_where="is_active = true",
        ),
    )


class SettlementEntityTypeEnum(str, enum.Enum):
    RESTAURANT = "RESTAURANT"
    DRIVER = "DRIVER"


class SettlementStatusEnum(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[SettlementEntityTypeEnum] = mapped_column(
        Enum(SettlementEntityTypeEnum), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )  # restaurants.id or users.id (driver)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")  # USD or VES
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    delivery_fees_collected: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    platform_fees_collected: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    adjustments: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[SettlementStatusEnum] = mapped_column(
        Enum(SettlementStatusEnum), nullable=False, default=SettlementStatusEnum.DRAFT, index=True
    )
    proof_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "period_start",
            "period_end",
            "currency",
            name="uq_settlement_entity_period_currency",
        ),
        Index(
            "ix_settlements_entity_type_id_period",
            "entity_type",
            "entity_id",
            "period_start",
            "period_end",
        ),
        Index("ix_settlements_status", "status"),
    )


class RefundTypeEnum(str, enum.Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    ADJUSTMENT = "ADJUSTMENT"


class RefundReasonEnum(str, enum.Enum):
    CANCELLED_PREPARING = "CANCELLED_PREPARING"
    CANCELLED_ON_THE_WAY = "CANCELLED_ON_THE_WAY"
    CUSTOMER_ABSENT = "CUSTOMER_ABSENT"
    DISPUTE = "DISPUTE"
    ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT"


class RefundStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[RefundTypeEnum] = mapped_column(Enum(RefundTypeEnum), nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    amount_ves: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[RefundReasonEnum] = mapped_column(Enum(RefundReasonEnum), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    proof_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RefundStatusEnum] = mapped_column(
        Enum(RefundStatusEnum), nullable=False, default=RefundStatusEnum.PENDING, index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("ix_refunds_order_id", "order_id"),
        Index("ix_refunds_status", "status"),
    )
