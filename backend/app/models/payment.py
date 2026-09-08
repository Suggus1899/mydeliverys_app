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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class PaymentPhaseEnum(str, enum.Enum):
    FIRST_HALF = "FIRST_HALF"
    SECOND_HALF = "SECOND_HALF"


class PaymentMethodEnum(str, enum.Enum):
    PAGO_MOVIL = "PAGO_MOVIL"
    BANK_TRANSFER = "BANK_TRANSFER"
    CASH_USD = "CASH_USD"
    CASH_VES = "CASH_VES"


class PaymentStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class ReconciliationStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    MATCHED = "MATCHED"
    DISCREPANCY = "DISCREPANCY"
    REFUNDED = "REFUNDED"
    ADJUSTED = "ADJUSTED"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phase: Mapped[PaymentPhaseEnum] = mapped_column(Enum(PaymentPhaseEnum), nullable=False)
    method: Mapped[PaymentMethodEnum] = mapped_column(Enum(PaymentMethodEnum), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # USD amount
    ves_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )  # VES amount if paid in VES
    exchange_rate_used: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    status: Mapped[PaymentStatusEnum] = mapped_column(
        Enum(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.PENDING, index=True
    )
    reference_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    origin_bank: Mapped[str | None] = mapped_column(String(50), nullable=True)
    proof_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciliation_status: Mapped[ReconciliationStatusEnum] = mapped_column(
        Enum(ReconciliationStatusEnum), nullable=False, default=ReconciliationStatusEnum.PENDING
    )
    discrepancy_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    idempotency_scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    order: Mapped["Order"] = relationship(back_populates="payments")
    verified_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="payments_verified", foreign_keys=[verified_by]
    )

    __table_args__ = (
        UniqueConstraint(
            "order_id", "phase", "idempotency_key", name="uq_payment_order_phase_idempotency"
        ),
        Index("ix_payments_order_id_phase", "order_id", "phase"),
        Index("ix_payments_status_phase", "status", "phase"),
        Index("ix_payments_idempotency", "idempotency_key", "idempotency_scope"),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope: Mapped[str] = mapped_column(String(50), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (Index("ix_idempotency_keys_expires_at", "expires_at"),)
