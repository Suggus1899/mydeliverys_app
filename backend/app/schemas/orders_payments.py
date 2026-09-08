from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Order Schemas
# =============================================================================


class OrderModifierResponse(BaseModel):
    modifier_id: UUID
    modifier_name: str
    extra_price: str

    model_config = ConfigDict(from_attributes=True)


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    unit_price: str
    total_price: str
    modifiers: list[OrderModifierResponse] = []

    model_config = ConfigDict(from_attributes=True)


class OrderPaymentResponse(BaseModel):
    id: UUID
    phase: str  # FIRST_HALF, SECOND_HALF
    method: str  # PAGO_MOVIL, BANK_TRANSFER, CASH_USD, CASH_VES
    amount: str
    ves_amount: str | None = None
    status: str  # PENDING, VERIFIED, REJECTED
    reference_number: str | None = None
    origin_bank: str | None = None
    verified_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderTrackingPoint(BaseModel):
    latitude: Decimal
    longitude: Decimal
    heading: float | None = None
    battery_level: int | None = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    customer_id: UUID
    restaurant_id: UUID
    driver_id: UUID | None = None
    delivery_address_id: UUID
    status: str
    subtotal_amount: str
    delivery_fee: str
    platform_fee: str
    total_amount: str
    first_half_amount: str
    second_half_amount: str
    delivery_distance_m: str
    cancellation_reason: str | None = None
    acknowledged_at: datetime | None = None
    arrived_at_restaurant_at: datetime | None = None
    arrived_at_customer_at: datetime | None = None
    exchange_rate: str
    exchange_rate_source: str
    exchange_rate_effective_date: str
    quote_snapshot: dict[str, Any]
    items: list[OrderItemResponse] = []
    payments: list[OrderPaymentResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderListItem(BaseModel):
    id: UUID
    order_number: str
    restaurant_name: str
    total_amount: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderStatusUpdate(BaseModel):
    status: str


class OrderCancelRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


# =============================================================================
# Payment Schemas
# =============================================================================


class PaymentReportRequest(BaseModel):
    phase: str = Field(..., pattern="^(FIRST_HALF|SECOND_HALF)$")
    method: str = Field(..., pattern="^(PAGO_MOVIL|BANK_TRANSFER|CASH_USD|CASH_VES)$")
    reference_number: str | None = Field(None, max_length=50)
    origin_bank: str | None = Field(None, max_length=50)
    proof_image_url: str | None = None
    amount_usd: Decimal | None = Field(None, ge=0)  # For driver cash collection
    amount_ves: Decimal | None = Field(None, ge=0)  # For driver cash collection in VES


class PaymentVerifyRequest(BaseModel):
    pass  # No body needed, just the payment_id in path


class PaymentRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class PaymentResponse(BaseModel):
    id: UUID
    order_id: UUID
    phase: str
    method: str
    amount: str
    ves_amount: str | None = None
    status: str
    reference_number: str | None = None
    origin_bank: str | None = None
    proof_image_url: str | None = None
    verified_by: UUID | None = None
    verified_at: datetime | None = None
    reconciliation_status: str
    discrepancy_amount: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PendingPaymentListItem(BaseModel):
    payment_id: UUID
    order_id: UUID
    order_number: str
    phase: str
    method: str
    amount_usd: str
    amount_ves: str | None = None
    reference_number: str | None = None
    origin_bank: str | None = None
    proof_image_url: str | None = None
    customer_name: str
    customer_phone: str
    created_at: datetime


# =============================================================================
# Driver Schemas
# =============================================================================


class DriverAvailabilityRequest(BaseModel):
    is_available: bool


class DriverOrderAcceptRequest(BaseModel):
    pass  # No body needed


class DriverOrderPickupRequest(BaseModel):
    pass  # No body needed


class DriverOrderArriveRestaurantRequest(BaseModel):
    pass  # No body needed


class DriverOrderArriveCustomerRequest(BaseModel):
    manual: bool = False
    evidence_image_url: str | None = None


class DriverCollectCashRequest(BaseModel):
    amount_usd: Decimal = Field(..., ge=0)
    amount_ves: Decimal | None = Field(None, ge=0)


class DriverConfirmDigitalRequest(BaseModel):
    method: str = Field(default="PAGO_MOVIL", pattern="^(PAGO_MOVIL|BANK_TRANSFER)$")
    reference_number: str = Field(..., min_length=4, max_length=50)
    origin_bank: str = Field(..., max_length=50)
    proof_image_url: str | None = None


class DriverReportAbsentRequest(BaseModel):
    evidence_image_url: str
    notes: str | None = None


class DriverReportIncidentRequest(BaseModel):
    type: str = Field(..., pattern="^(ACCIDENT|BREAKDOWN)$")
    evidence_image_url: str | None = None
    notes: str | None = None


class DriverOrderDetail(BaseModel):
    id: UUID
    order_number: str
    status: str
    restaurant_name: str
    restaurant_address: str
    restaurant_latitude: Decimal
    restaurant_longitude: Decimal
    customer_name: str
    customer_phone: str
    customer_address: str
    customer_latitude: Decimal
    customer_longitude: Decimal
    total_amount: str
    first_half_amount: str
    second_half_amount: str
    second_half_ves: str | None = None
    items: list[OrderItemResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DriverEarningsResponse(BaseModel):
    period: str
    orders_completed: int
    total_cash_usd: str
    total_cash_ves: str
    total_pago_movil: str
    platform_fees: str
    net_amount: str


# =============================================================================
# Admin Schemas
# =============================================================================


class AdminRestaurantStaffCreate(BaseModel):
    restaurant_id: UUID
    phone: str = Field(..., max_length=20)
    full_name: str = Field(..., max_length=120)
    temp_password: str = Field(..., min_length=8)


class AdminDriverCreate(BaseModel):
    phone: str = Field(..., max_length=20)
    full_name: str = Field(..., max_length=120)
    temp_password: str = Field(..., min_length=8)
    vehicle_info: str | None = None


class AdminOrderReassignRequest(BaseModel):
    new_driver_id: UUID
    evidence_image_url: str | None = None


class AdminRefundCreate(BaseModel):
    order_id: UUID
    payment_id: UUID
    type: str = Field(..., pattern="^(FULL|PARTIAL|ADJUSTMENT)$")
    reason: str = Field(
        ...,
        pattern="^(CANCELLED_PREPARING|CANCELLED_ON_THE_WAY|CUSTOMER_ABSENT|DISPUTE|ADMIN_ADJUSTMENT)$",
    )
    amount_usd: Decimal = Field(..., ge=0)
    proof_image_url: str | None = None


class AdminRefundUpdate(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED)$")


class AdminDiscrepancyRequest(BaseModel):
    reported_amount: Decimal = Field(..., ge=0)


class AdminSettlementCreate(BaseModel):
    entity_type: str = Field(..., pattern="^(RESTAURANT|DRIVER)$")
    entity_id: UUID
    period_start: str  # YYYY-MM-DD
    period_end: str  # YYYY-MM-DD
    currency: str = Field(default="USD", pattern="^(USD|VES)$")


class AdminSettlementUpdate(BaseModel):
    status: str = Field(..., pattern="^(CONFIRMED|PAID|CANCELLED)$")
    proof_image_url: str | None = None


class AdminSettlementResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    entity_name: str
    period_start: str
    period_end: str
    currency: str
    gross_amount: str
    commission_amount: str
    delivery_fees_collected: str
    platform_fees_collected: str
    adjustments: str
    net_amount: str
    status: str
    proof_image_url: str | None = None
    notes: str | None = None
    created_by: UUID
    confirmed_by: UUID | None = None
    created_at: datetime
    confirmed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ExchangeRateHealthResponse(BaseModel):
    last_valid_rate: str | None = None
    last_valid_queried_at: datetime | None = None
    last_valid_effective_date: str | None = None
    seconds_since_last_valid: int | None = None
    consecutive_failures: int
    is_blocking_new_orders: bool


# =============================================================================
# Tracking Schemas
# =============================================================================


class DriverLocationUpdate(BaseModel):
    latitude: Decimal = Field(..., ge=-90, le=90)
    longitude: Decimal = Field(..., ge=-180, le=180)
    heading: float | None = Field(None, ge=0, le=360)
    order_id: UUID
    battery_level: int | None = Field(None, ge=0, le=100)


class LocationHistoryBatch(BaseModel):
    order_id: UUID
    points: list[OrderTrackingPoint]


class GeofenceEventResponse(BaseModel):
    id: UUID
    order_id: UUID
    driver_id: UUID
    event_type: str
    triggered_by: str
    distance_m: str | None = None
    accuracy_m: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
