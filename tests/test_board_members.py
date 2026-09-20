"""Contract checks for board-member management APIs."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.board_members.schemas import BoardMemberCreateRequest


def test_board_member_request_parses_dates() -> None:
    payload = BoardMemberCreateRequest(
        association_id="association-1",
        account_id="account-1",
        term_start_date="2026-01-01",
        term_end_date="2026-12-31",
    )
    assert payload.term_start_date == date(2026, 1, 1)


def test_board_member_request_requires_identifiers() -> None:
    with pytest.raises(ValidationError):
        BoardMemberCreateRequest(
            association_id=" ",
            account_id="account-1",
            term_start_date="2026-01-01",
            term_end_date="2026-12-31",
        )


def test_board_member_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}
    expected = {
        ("GET", "/api/admin/board-members"),
        ("POST", "/api/admin/board-members"),
        ("PUT", "/api/admin/board-members/{membership_id}/end-term"),
        ("GET", "/api/admin/associations/{association_id}/homeowners"),
        ("GET", "/api/associations/{association_id}/board-members"),
    }
    assert expected <= routes
