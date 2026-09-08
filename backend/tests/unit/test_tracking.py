from decimal import Decimal
from uuid import uuid4

from app.services.tracking import (
    EPHEMERAL_TTL,
    GEOFENCE_RADIUS_M,
    HISTORY_INTERVAL_S,
    ephemeral_key,
    location_channel,
)


class TestTrackingConstants:
    def test_ephemeral_ttl_10min(self) -> None:
        assert EPHEMERAL_TTL == 600

    def test_history_interval_3min(self) -> None:
        assert HISTORY_INTERVAL_S == 180

    def test_geofence_100m(self) -> None:
        assert GEOFENCE_RADIUS_M == 100

    def test_key_format(self) -> None:
        oid = uuid4()
        assert ephemeral_key(oid) == f"driver:location:{oid}"
        assert location_channel(oid) == f"order:{oid}:location"


class TestHaversineSanity:
    def test_same_point_zero(self) -> None:
        from app.services.orders import _haversine_m

        d = _haversine_m(Decimal("9.75"), Decimal("-67.35"), Decimal("9.75"), Decimal("-67.35"))
        assert d == Decimal("0.00")

    def test_known_distance_positive(self) -> None:
        from app.services.orders import _haversine_m

        # Av Bolivar -> Los Rosales aprox 1-5km
        d = _haversine_m(Decimal("9.75"), Decimal("-67.35"), Decimal("9.76"), Decimal("-67.34"))
        assert Decimal("500") < d < Decimal("5000")
