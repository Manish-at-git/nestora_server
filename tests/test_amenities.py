"""Fast checks for amenity contracts and legacy route coverage."""

import pytest
from pydantic import ValidationError

from app.modules.amenities.schemas import AmenityBookingRequest, AmenityCreateRequest


def test_booking_requires_a_valid_time_range_and_wallet_pin() -> None:
    with pytest.raises(ValidationError):
        AmenityBookingRequest(
            booking_date="2026-09-20",
            start_time="10:00",
            end_time="09:00",
            duration_hours=1,
            pin="1234",
        )
    with pytest.raises(ValidationError):
        AmenityBookingRequest(
            booking_date="2026-09-20",
            start_time="10:00",
            end_time="11:00",
            duration_hours=1,
        )


def test_amenity_name_is_trimmed() -> None:
    assert AmenityCreateRequest(name="  Pool  ", charges=0).name == "Pool"


def test_amenity_legacy_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}
    expected = {
        ("GET", "/api/admin/associations/{association_id}/amenities"),
        ("POST", "/api/admin/associations/{association_id}/amenities"),
        ("PUT", "/api/admin/associations/{association_id}/amenities/{amenity_id}"),
        ("DELETE", "/api/admin/associations/{association_id}/amenities/{amenity_id}"),
        ("GET", "/api/admin/associations/{association_id}/amenity-bookings"),
        ("GET", "/api/associations/{association_id}/amenities"),
        ("GET", "/api/amenities/{amenity_id}/bookings"),
        ("GET", "/api/amenities/my-bookings"),
        ("POST", "/api/amenities/{amenity_id}/book"),
    }
    assert expected <= routes

