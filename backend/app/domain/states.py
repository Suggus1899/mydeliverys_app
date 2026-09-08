from enum import StrEnum

from app.domain.errors import DomainError


class OrderStatus(StrEnum):
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


TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PAYMENT_1_PENDING: frozenset(
        {OrderStatus.PAYMENT_1_VERIFYING, OrderStatus.CANCELLED}
    ),
    OrderStatus.PAYMENT_1_VERIFYING: frozenset(
        {
            OrderStatus.PAYMENT_1_PENDING,
            OrderStatus.PREPARING,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.PREPARING: frozenset(
        {OrderStatus.READY_FOR_PICKUP, OrderStatus.CANCELLED_WITH_REFUND}
    ),
    OrderStatus.READY_FOR_PICKUP: frozenset(
        {OrderStatus.ON_THE_WAY, OrderStatus.CANCELLED_WITH_REFUND}
    ),
    OrderStatus.ON_THE_WAY: frozenset(
        {OrderStatus.ARRIVED_AT_CUSTOMER, OrderStatus.CANCELLED_WITH_REFUND}
    ),
    OrderStatus.ARRIVED_AT_CUSTOMER: frozenset(
        {OrderStatus.PAYMENT_2_VERIFYING, OrderStatus.DELIVERED, OrderStatus.DELIVERY_FAILED}
    ),
    OrderStatus.PAYMENT_2_VERIFYING: frozenset(
        {OrderStatus.ARRIVED_AT_CUSTOMER, OrderStatus.DELIVERED}
    ),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.CANCELLED_WITH_REFUND: frozenset(),
    OrderStatus.DELIVERY_FAILED: frozenset(),
}


def transition(
    current: OrderStatus,
    target: OrderStatus,
    *,
    first_verified: bool = False,
    second_verified: bool = False,
) -> OrderStatus:
    if target not in TRANSITIONS[current]:
        raise DomainError(
            "INVALID_STATE_TRANSITION", "La transición del pedido no está permitida.", 409
        )
    if target == OrderStatus.PREPARING and not first_verified:
        raise DomainError("FIRST_PAYMENT_REQUIRED", "Falta verificar el primer pago.", 409)
    if target == OrderStatus.DELIVERED and not second_verified:
        raise DomainError("SECOND_PAYMENT_REQUIRED", "Falta verificar el segundo pago.", 409)
    return target
