from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from app.domain.errors import DomainError

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("99999999.99")


def money(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise DomainError("INVALID_AMOUNT", "El monto debe ser decimal, finito y no negativo.")
    result = value.quantize(CENT, rounding=ROUND_HALF_UP)
    if result > MAX_AMOUNT:
        raise DomainError("INVALID_AMOUNT", "El monto supera el límite permitido.")
    return result


@dataclass(frozen=True)
class PaymentBreakdown:
    total: Decimal
    first_half: Decimal
    second_half: Decimal


def split_payment(total: Decimal) -> PaymentBreakdown:
    total = money(total)
    if total <= 0:
        raise DomainError("INVALID_AMOUNT", "El total debe ser mayor a cero.")
    first = (total / 2).quantize(CENT, rounding=ROUND_CEILING)
    return PaymentBreakdown(total, first, total - first)


def line_total(base: Decimal, extras: list[Decimal], quantity: int) -> Decimal:
    if isinstance(quantity, bool) or quantity < 1 or quantity > 99:
        raise DomainError("INVALID_QUANTITY", "La cantidad debe estar entre 1 y 99.")
    return money((money(base) + sum((money(extra) for extra in extras), Decimal(0))) * quantity)


def to_ves(amount: Decimal, rate: Decimal) -> Decimal:
    if not isinstance(rate, Decimal) or not rate.is_finite() or rate <= 0:
        raise DomainError("INVALID_RATE", "La tasa de cambio no es válida.")
    return money(money(amount) * rate)


def settlement(
    total: Decimal, delivery_fee: Decimal, platform_fee: Decimal, commission_rate: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    if not commission_rate.is_finite() or not Decimal(0) <= commission_rate <= Decimal(100):
        raise DomainError("INVALID_COMMISSION", "La comisión debe estar entre 0 y 100.")
    subtotal = money(total) - money(delivery_fee) - money(platform_fee)
    subtotal = money(subtotal)
    commission = money(subtotal * commission_rate / 100)
    return subtotal - commission, money(delivery_fee), money(platform_fee) + commission


def discrepancy(expected: Decimal, reported: Decimal) -> Decimal:
    """Diferencia reportado - esperado. Positivo = excedente, negativo = faltante."""
    return money(reported) - money(expected)
