"""Fast checks for announcement contracts and legacy route coverage."""

import pytest
from pydantic import ValidationError

from app.modules.announcements.schemas import AnnouncementCommentRequest, AnnouncementCreateRequest


def test_category_is_normalized_for_legacy_clients() -> None:
    payload = AnnouncementCreateRequest(title="Notice", body="Details", category="General")
    assert payload.category.value == "general"


def test_comment_cannot_be_blank() -> None:
    with pytest.raises(ValidationError):
        AnnouncementCommentRequest(comment="  ")


def test_announcement_legacy_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}
    expected = {
        ("GET", "/api/announcements"),
        ("POST", "/api/announcements"),
        ("POST", "/api/announcements/{announcement_id}/like"),
        ("POST", "/api/announcements/{announcement_id}/comment"),
        ("GET", "/api/announcements/{announcement_id}/comments"),
        ("PUT", "/api/admin/announcements/{announcement_id}"),
        ("DELETE", "/api/admin/announcements/{announcement_id}"),
    }
    assert expected <= routes

