from decimal import ROUND_CEILING, Decimal

import pytest

from app.domain.errors import DomainError
from app.domain.financial import (
    PaymentBreakdown,
    discrepancy,
    line_total,
    money,
    settlement,
    split_payment,
    to_ves,
)


class TestMoney:
    """Tests for money() quantization and validation."""

    def test_money_valid_positive(self):
        result = money(Decimal("10.50"))
        assert result == Decimal("10.50")

    def test_money_quantizes_to_cents(self):
        result = money(Decimal("10.555"))
        assert result == Decimal("10.56")  # ROUND_HALF_UP

    def test_money_quantizes_down(self):
        result = money(Decimal("10.554"))
        assert result == Decimal("10.55")

    def test_money_zero(self):
        result = money(Decimal("0"))
        assert result == Decimal("0.00")

    def test_money_negative_raises(self):
        with pytest.raises(DomainError) as exc:
            money(Decimal("-1.00"))
        assert exc.value.code == "INVALID_AMOUNT"

    def test_money_non_finite_raises(self):
        with pytest.raises(DomainError) as exc:
            money(Decimal("Infinity"))
        assert exc.value.code == "INVALID_AMOUNT"

    def test_money_non_decimal_raises(self):
        with pytest.raises(DomainError) as exc:
            money("10.50")  # type: ignore
        assert exc.value.code == "INVALID_AMOUNT"

    def test_money_exceeds_max_raises(self):
        with pytest.raises(DomainError) as exc:
            money(Decimal("100000000.00"))
        assert exc.value.code == "INVALID_AMOUNT"


class TestSplitPayment:
    """Tests for 50/50 payment split with odd cent rule."""

    def test_split_even_amount(self):
        """$20.00 -> $10.00 + $10.00"""
        result = split_payment(Decimal("20.00"))
        assert isinstance(result, PaymentBreakdown)
        assert result.total == Decimal("20.00")
        assert result.first_half == Decimal("10.00")
        assert result.second_half == Decimal("10.00")
        assert result.first_half + result.second_half == result.total

    def test_split_odd_cent_amount(self):
        """$15.01 -> $7.51 + $7.50 (odd cent goes to first)"""
        result = split_payment(Decimal("15.01"))
        assert result.total == Decimal("15.01")
        assert result.first_half == Decimal("7.51")
        assert result.second_half == Decimal("7.50")
        assert result.first_half + result.second_half == result.total

    def test_split_minimal_amount(self):
        """$0.01 -> $0.01 + $0.00"""
        result = split_payment(Decimal("0.01"))
        assert result.total == Decimal("0.01")
        assert result.first_half == Decimal("0.01")
        assert result.second_half == Decimal("0.00")
        assert result.first_half + result.second_half == result.total

    def test_split_various_amounts(self):
        test_cases = [
            ("10.00", "5.00", "5.00"),
            ("10.01", "5.01", "5.00"),
            ("10.02", "5.01", "5.01"),
            ("10.03", "5.02", "5.01"),
            ("100.00", "50.00", "50.00"),
            ("100.01", "50.01", "50.00"),
            ("0.02", "0.01", "0.01"),
            ("0.03", "0.02", "0.01"),
            ("99999999.99", "50000000.00", "49999999.99"),
        ]
        for total_str, first_str, second_str in test_cases:
            total = Decimal(total_str)
            result = split_payment(total)
            assert result.total == total, f"Failed for {total_str}: total mismatch"
            assert result.first_half == Decimal(first_str), (
                f"Failed for {total_str}: first_half mismatch"
            )
            assert result.second_half == Decimal(second_str), (
                f"Failed for {total_str}: second_half mismatch"
            )
            assert result.first_half + result.second_half == total, (
                f"Failed for {total_str}: sum mismatch"
            )

    def test_split_zero_raises(self):
        with pytest.raises(DomainError) as exc:
            split_payment(Decimal("0"))
        assert exc.value.code == "INVALID_AMOUNT"

    def test_split_negative_raises(self):
        with pytest.raises(DomainError) as exc:
            split_payment(Decimal("-10.00"))
        assert exc.value.code == "INVALID_AMOUNT"

    def test_split_uses_ceiling_for_first_half(self):
        """Verify the ceiling formula is used."""
        total = Decimal("15.01")
        # Manual calculation: ceil(15.01 / 2 * 100) / 100 = ceil(7.505) / 100 = 8 / 100 = 0.08... wait
        # Actually: ceil(15.01 / 2 * 100) = ceil(750.5) = 751, then / 100 = 7.51
        expected_first = (total / 2).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        result = split_payment(total)
        assert result.first_half == expected_first


class TestLineTotal:
    """Tests for line_total calculation with modifiers and quantity."""

    def test_line_total_simple(self):
        """Product only, no modifiers, qty=1."""
        result = line_total(Decimal("5.00"), [], 1)
        assert result == Decimal("5.00")

    def test_line_total_with_quantity(self):
        """Product only, qty=3."""
        result = line_total(Decimal("5.00"), [], 3)
        assert result == Decimal("15.00")

    def test_line_total_with_modifiers(self):
        """Product + modifiers, qty=1."""
        result = line_total(Decimal("5.00"), [Decimal("0.50"), Decimal("0.75")], 1)
        assert result == Decimal("6.25")

    def test_line_total_with_modifiers_and_quantity(self):
        """Product + modifiers, qty=2."""
        result = line_total(Decimal("5.00"), [Decimal("0.50")], 2)
        assert result == Decimal("11.00")

    def test_line_total_zero_quantity_raises(self):
        with pytest.raises(DomainError) as exc:
            line_total(Decimal("5.00"), [], 0)
        assert exc.value.code == "INVALID_QUANTITY"

    def test_line_total_negative_quantity_raises(self):
        with pytest.raises(DomainError) as exc:
            line_total(Decimal("5.00"), [], -1)
        assert exc.value.code == "INVALID_QUANTITY"

    def test_line_total_excessive_quantity_raises(self):
        with pytest.raises(DomainError) as exc:
            line_total(Decimal("5.00"), [], 100)
        assert exc.value.code == "INVALID_QUANTITY"

    def test_line_total_bool_quantity_raises(self):
        with pytest.raises(DomainError) as exc:
            line_total(Decimal("5.00"), [], True)  # type: ignore
        assert exc.value.code == "INVALID_QUANTITY"

    def test_line_total_modifier_quantization(self):
        """Modifiers are quantized individually before sum."""
        result = line_total(Decimal("5.00"), [Decimal("0.555"), Decimal("0.555")], 1)
        # 0.555 -> 0.56 each, sum = 1.12, + 5.00 = 6.12
        assert result == Decimal("6.12")


class TestToVes:
    """Tests for USD to VES conversion."""

    def test_to_ves_valid(self):
        result = to_ves(Decimal("10.00"), Decimal("36.50"))
        assert result == Decimal("365.00")

    def test_to_ves_quantizes(self):
        result = to_ves(Decimal("10.00"), Decimal("36.5555"))
        assert result == Decimal("365.56")

    def test_to_ves_zero_amount(self):
        result = to_ves(Decimal("0"), Decimal("36.50"))
        assert result == Decimal("0.00")

    def test_to_ves_invalid_rate_zero(self):
        with pytest.raises(DomainError) as exc:
            to_ves(Decimal("10.00"), Decimal("0"))
        assert exc.value.code == "INVALID_RATE"

    def test_to_ves_invalid_rate_negative(self):
        with pytest.raises(DomainError) as exc:
            to_ves(Decimal("10.00"), Decimal("-1.00"))
        assert exc.value.code == "INVALID_RATE"

    def test_to_ves_invalid_rate_non_finite(self):
        with pytest.raises(DomainError) as exc:
            to_ves(Decimal("10.00"), Decimal("Infinity"))
        assert exc.value.code == "INVALID_RATE"

    def test_to_ves_non_decimal_rate(self):
        with pytest.raises(DomainError) as exc:
            to_ves(Decimal("10.00"), "36.50")  # type: ignore
        assert exc.value.code == "INVALID_RATE"


class TestSettlement:
    """Tests for settlement calculation (restaurant payout)."""

    def test_settlement_basic(self):
        """Basic settlement: total=100, delivery=5, platform=2, commission=15%"""
        subtotal, delivery, platform = settlement(
            total=Decimal("100.00"),
            delivery_fee=Decimal("5.00"),
            platform_fee=Decimal("2.00"),
            commission_rate=Decimal("15.00"),
        )
        # subtotal = 100 - 5 - 2 = 93
        # commission = 93 * 15% = 13.95
        # restaurant gets = 93 - 13.95 = 79.05
        assert subtotal == Decimal("79.05")
        assert delivery == Decimal("5.00")
        assert platform == Decimal("15.95")  # 2.00 + 13.95

    def test_settlement_zero_commission(self):
        subtotal, delivery, platform = settlement(
            total=Decimal("100.00"),
            delivery_fee=Decimal("5.00"),
            platform_fee=Decimal("2.00"),
            commission_rate=Decimal("0"),
        )
        assert subtotal == Decimal("93.00")
        assert delivery == Decimal("5.00")
        assert platform == Decimal("2.00")

    def test_settlement_max_commission(self):
        subtotal, delivery, platform = settlement(
            total=Decimal("100.00"),
            delivery_fee=Decimal("5.00"),
            platform_fee=Decimal("2.00"),
            commission_rate=Decimal("100.00"),
        )
        # subtotal = 93, commission = 93, restaurant gets = 0
        assert subtotal == Decimal("0.00")
        assert delivery == Decimal("5.00")
        assert platform == Decimal("95.00")

    def test_settlement_invalid_commission_negative(self):
        with pytest.raises(DomainError) as exc:
            settlement(
                total=Decimal("100.00"),
                delivery_fee=Decimal("5.00"),
                platform_fee=Decimal("2.00"),
                commission_rate=Decimal("-1"),
            )
        assert exc.value.code == "INVALID_COMMISSION"

    def test_settlement_invalid_commission_over_100(self):
        with pytest.raises(DomainError) as exc:
            settlement(
                total=Decimal("100.00"),
                delivery_fee=Decimal("5.00"),
                platform_fee=Decimal("2.00"),
                commission_rate=Decimal("101"),
            )
        assert exc.value.code == "INVALID_COMMISSION"

    def test_settlement_non_finite_commission(self):
        with pytest.raises(DomainError) as exc:
            settlement(
                total=Decimal("100.00"),
                delivery_fee=Decimal("5.00"),
                platform_fee=Decimal("2.00"),
                commission_rate=Decimal("Infinity"),
            )
        assert exc.value.code == "INVALID_COMMISSION"


class TestDiscrepancy:
    def test_exact_match_zero(self):
        assert discrepancy(Decimal("7.51"), Decimal("7.51")) == Decimal("0.00")

    def test_excess_positive(self):
        assert discrepancy(Decimal("7.50"), Decimal("8.00")) == Decimal("0.50")

    def test_shortfall_negative(self):
        assert discrepancy(Decimal("7.51"), Decimal("7.00")) == Decimal("-0.51")
