"""Contract checks for visitor and delivery management APIs."""

from datetime import date, time

from app.modules.visitor_management.schemas import PreApprovedVisitorRequest, VisitorRequest


def test_preapproved_visitor_request_contract() -> None:
    payload = PreApprovedVisitorRequest(
        visitor_name="Asha Rao",
        mobile="9876543210",
        visitor_type="Guest",
        visit_date=date.today(),
        start_time=time(9),
        end_time=time(18),
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


def test_visitor_routes_are_registered(monkeypatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/resident/preapproved-visitors" in paths
    assert "/api/security/visitors/checkin-list" in paths
    assert "/api/security/deliveries" in paths
