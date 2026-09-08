from decimal import Decimal

from app.core.security import normalize_phone
from app.services.pricing import build_payment_breakdown


class TestNormalizePhone:
    def test_venezuelan_mobile_0414(self) -> None:
        assert normalize_phone("04141234567") == "+584141234567"

    def test_with_country_code(self) -> None:
        assert normalize_phone("+584141234567") == "+584141234567"

    def test_with_spaces_dashes(self) -> None:
        assert normalize_phone("+58 414-123-4567") == "+584141234567"

    def test_invalid_length(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            normalize_phone("123")


class TestPaymentBreakdownVes:
    def test_even_total_ves_conserved(self) -> None:
        b = build_payment_breakdown(Decimal("20.00"), Decimal("36.50"))
        assert b["first_half"] == "10.00"
        assert b["second_half"] == "10.00"
        assert Decimal(b["first_half_ves"]) + Decimal(b["second_half_ves"]) == Decimal(
            b["total_ves"]
        )

    def test_odd_total_ves_conserved(self) -> None:
        b = build_payment_breakdown(Decimal("15.01"), Decimal("36.50"))
        assert b["first_half"] == "7.51"
        assert b["second_half"] == "7.50"
        total_ves = Decimal(b["total_ves"])
        assert Decimal(b["first_half_ves"]) + Decimal(b["second_half_ves"]) == total_ves

    def test_minimal_total(self) -> None:
        b = build_payment_breakdown(Decimal("0.01"), Decimal("40.00"))
        assert b["first_half"] == "0.01"
        assert b["second_half"] == "0.00"
