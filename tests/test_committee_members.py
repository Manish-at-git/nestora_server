"""Contract checks for committee-member management and directory APIs."""

import pytest
from pydantic import ValidationError

from app.modules.committees.schemas import CommitteeMemberAssignRequest, CommitteeMemberUpdateRequest


def test_committee_member_dates_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        CommitteeMemberAssignRequest(
            committee_id="committee-1",
            user_id="user-1",
            start_date="2026-10-01",
            end_date="2026-09-01",
        )


def test_committee_member_update_dates_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        CommitteeMemberUpdateRequest(start_date="2026-10-01", end_date="2026-09-01")


def test_committee_member_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}
    expected = {
        ("GET", "/api/admin/committee-members"),
        ("POST", "/api/admin/committee-members"),
        ("PUT", "/api/admin/committee-members/{committee_id}/{user_id}"),
        ("DELETE", "/api/admin/committee-members/{committee_id}/{user_id}"),
        ("DELETE", "/api/admin/committee-members/{member_id}"),
        ("GET", "/api/associations/{association_id}/committee-members"),
    }
    assert expected <= routes
