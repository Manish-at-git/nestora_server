"""Contract checks for visitor and delivery management APIs."""

from datetime import date, datetime, time, timedelta

import pytest
from pydantic import ValidationError

from app.core.constants import FeatureCode, RoleCode
from app.modules.visitor_management.constants import RESIDENT_VISITOR_ROLES
from app.seed import (
    RESIDENT_VISITOR_PERMISSION_MATRIX,
    SECURITY_VISITOR_PERMISSION_MATRIX,
)
from app.modules.visitor_management.schemas import (
    CheckInRequest,
    PreApprovedVisitorRequest,
    VisitorRequest,
)
from app.modules.visitor_management.service import _effective_pass_status, _scheduled_datetime


def test_preapproved_visitor_request_contract() -> None:
    payload = PreApprovedVisitorRequest(
        visitor_name="Asha Rao",
        mobile="9876543210",
        visitor_type="Guest",
        visit_date=date.today() + timedelta(days=1),
        start_time=time(9),
        end_time=time(18),
        number_of_visitors=1,
    )
    assert payload.number_of_visitors == 1
    assert payload.pass_type == "Single Entry"


def test_security_request_contract() -> None:
    payload = VisitorRequest(
        mobile="9876543210",
        name="Asha Rao",
        visitor_type="Guest",
        unit_id="unit-1",
        purpose="Visit",
    )
    assert payload.number_of_visitors == 1


def test_preapproved_visitor_request_rejects_a_past_schedule() -> None:
    with pytest.raises(ValidationError, match="Visit date and start time must be in the future"):
        PreApprovedVisitorRequest(
            visitor_name="Asha Rao",
            mobile="9876543210",
            visitor_type="Guest",
            visit_date=date.today() - timedelta(days=1),
            start_time=time(9),
            end_time=time(18),
            number_of_visitors=1,
        )


def test_check_in_request_accepts_visitor_otp() -> None:
    payload = CheckInRequest(otp="123456", gate="Main Gate")
    assert payload.otp == "123456"
    assert payload.gate == "Main Gate"


def test_scheduled_datetime_normalizes_mysql_time_delta() -> None:
    visit_date = date(2026, 10, 2)
    assert _scheduled_datetime(visit_date, timedelta(hours=9, minutes=30)) == datetime(
        2026,
        10,
        2,
        9,
        30,
    )


def test_active_pass_with_a_past_visit_date_is_effectively_expired() -> None:
    visitor_pass = _effective_pass_status(
        {"status": "Active", "visit_date": date.today() - timedelta(days=1)}
    )
    assert visitor_pass["status"] == "Expired"


def test_used_pass_with_a_past_visit_date_retains_used_status() -> None:
    visitor_pass = _effective_pass_status(
        {"status": "Used", "visit_date": date.today() - timedelta(days=1)}
    )
    assert visitor_pass["status"] == "Used"


def test_resident_visitor_roles_are_explicit() -> None:
    assert set(RESIDENT_VISITOR_ROLES) == {
        RoleCode.HOMEOWNER,
        RoleCode.TENANT,
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
    }


def test_preapproved_visitor_permission_matrix_is_role_specific() -> None:
    assert RESIDENT_VISITOR_PERMISSION_MATRIX[FeatureCode.PRE_APPROVED_VISITORS] == (
        True,
        True,
        True,
        True,
    )
    assert SECURITY_VISITOR_PERMISSION_MATRIX[FeatureCode.PRE_APPROVED_VISITORS] == (
        True,
        False,
        True,
        False,
    )
    assert SECURITY_VISITOR_PERMISSION_MATRIX[FeatureCode.GATE_CONSOLE] == (
        True,
        True,
        True,
        False,
    )
    assert FeatureCode.LEGACY_ACTIVE_VISITORS not in SECURITY_VISITOR_PERMISSION_MATRIX


def test_visitor_routes_are_registered(monkeypatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/resident/preapproved-visitors" in paths
    assert "/api/security/visitors/checkin-list" in paths
    assert "/api/security/deliveries" in paths
    assert "/api/resident/visitors/history" in paths
    assert "/api/resident/visitor/requests/history" in paths
    assert "/api/security/visitors/active" in paths
    assert "/api/security/visitor/requests" in paths
    assert "/api/security/visitor/requests/history" in paths
    assert "/api/security/visitor/{visit_id}/check-in" in paths
    assert "/api/security/visitor/{visit_id}/check-out" in paths
