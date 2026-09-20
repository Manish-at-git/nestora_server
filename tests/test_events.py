"""Contract checks for the modular Events API."""

import pytest
from pydantic import ValidationError

from app.modules.events.schemas import EventCommentRequest, EventCreateRequest, RSVPRequest


def test_event_dates_are_validated() -> None:
    with pytest.raises(ValidationError):
        EventCreateRequest(title="Community", starts_at="not-a-date")


def test_event_comment_cannot_be_blank() -> None:
    with pytest.raises(ValidationError):
        EventCommentRequest(comment="  ")


def test_event_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}
    expected = {
        ("GET", "/api/events"),
        ("POST", "/api/events"),
        ("PUT", "/api/admin/events/{event_id}"),
        ("DELETE", "/api/admin/events/{event_id}"),
        ("POST", "/api/admin/events"),
        ("GET", "/api/admin/events/{event_id}/rsvps"),
        ("POST", "/api/events/{event_id}/rsvp"),
        ("DELETE", "/api/events/{event_id}/rsvp"),
        ("POST", "/api/events/{event_id}/like"),
        ("GET", "/api/events/{event_id}/comments"),
        ("POST", "/api/events/{event_id}/comments"),
    }
    assert expected <= routes


def test_rsvp_status_contract() -> None:
    assert RSVPRequest(status="going").status.value == "going"
