# Import Base from core.database to avoid circular import
from app.core.database import Base
from app.models.audit import AuditLog, OrderEvent
from app.models.financial import (
    DeliveryFeeTier,
    ExchangeRate,
    PlatformFeeConfig,
    Refund,
    Settlement,
)
from app.models.order import Order, OrderItem, OrderModifier, OrderReservation, OrderStatusEnum
from app.models.payment import (
    IdempotencyKey,
    Payment,
    PaymentMethodEnum,
    PaymentPhaseEnum,
    PaymentStatusEnum,
)
from app.models.restaurant import Category, Modifier, ModifierGroup, Product, Restaurant
from app.models.tracking import DeliveryTracking, DriverLocationEphemeral, GeofenceEvent

# Base is defined in core.database, import it there to avoid circular imports
# This file just re-exports all models
# Import all models to ensure they're registered with Base.metadata
# This is needed for Alembic autogenerate to work
from app.models.user import RestaurantStaff, User, UserAddress, UserSession

__all__ = [
    "Base",
    "User",
    "UserAddress",
    "UserSession",
    "RestaurantStaff",
    "Restaurant",
    "Category",
    "Product",
    "ModifierGroup",
    "Modifier",
    "Order",
    "OrderItem",
    "OrderModifier",
    "OrderReservation",
    "OrderStatusEnum",
    "Payment",
    "PaymentPhaseEnum",
    "PaymentMethodEnum",
    "PaymentStatusEnum",
    "IdempotencyKey",
    "DeliveryTracking",
    "DriverLocationEphemeral",
    "GeofenceEvent",
    "ExchangeRate",
    "DeliveryFeeTier",
    "PlatformFeeConfig",
    "Settlement",
    "Refund",
    "AuditLog",
    "OrderEvent",
]
