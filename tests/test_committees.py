"""Fast checks for committee contracts and legacy route coverage."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.constants import RoleCode
from app.modules.committees.schemas import CommitteeCreateRequest, CommitteeChatMessageRequest
from app.modules.committees.service import CommitteeService


@pytest.mark.parametrize("role_code", [RoleCode.HOMEOWNER, RoleCode.TENANT])
async def test_residents_list_only_committees_from_their_own_association(
    role_code: RoleCode,
) -> None:
    service = CommitteeService(AsyncMock())
    account = SimpleNamespace(
        id="resident-account",
        user_id="resident-user",
        role=SimpleNamespace(code=role_code.value),
    )
    expected = [{"id": "committee-1", "association_id": "association-1"}]
    service.repository.member_association_id = AsyncMock(return_value="association-1")
    service.repository.list_committees = AsyncMock(return_value=expected)

    result = await service.list(account)

    assert result == expected
    service.repository.member_association_id.assert_awaited_once_with(account)
    service.repository.list_committees.assert_awaited_once_with(["association-1"])


@pytest.mark.parametrize("role_code", [RoleCode.HOMEOWNER, RoleCode.TENANT])
async def test_residents_cannot_list_committees_from_another_association(
    role_code: RoleCode,
) -> None:
    service = CommitteeService(AsyncMock())
    account = SimpleNamespace(
        id="resident-account",
        user_id="resident-user",
        role=SimpleNamespace(code=role_code.value),
    )
    service.repository.member_association_id = AsyncMock(return_value="association-1")
    service.repository.list_committees = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.list(account, "association-2")

    assert error.value.status_code == 403
    service.repository.list_committees.assert_not_awaited()


@pytest.mark.parametrize("role_code", [RoleCode.HOMEOWNER, RoleCode.TENANT])
async def test_unmapped_residents_receive_no_committees(role_code: RoleCode) -> None:
    service = CommitteeService(AsyncMock())
    account = SimpleNamespace(
        id="resident-account",
        user_id="resident-user",
        role=SimpleNamespace(code=role_code.value),
    )
    service.repository.member_association_id = AsyncMock(return_value=None)
    service.repository.list_committees = AsyncMock(return_value=[])

    result = await service.list(account)

    assert result == []
    service.repository.list_committees.assert_awaited_once_with([])


def test_committee_dates_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        CommitteeCreateRequest(
            association_id="association",
            name="Resident Welfare Committee",
            start_date="2026-09-20",
            end_date="2026-09-19",
        )


def test_chat_message_requires_non_blank_text() -> None:
    with pytest.raises(ValidationError):
        CommitteeChatMessageRequest(message="  ")


def test_committee_legacy_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}
    expected = {
        ("GET", "/api/admin/committees"),
        ("POST", "/api/admin/committees"),
        ("PUT", "/api/admin/committees/{committee_id}"),
        ("DELETE", "/api/admin/committees/{committee_id}"),
        ("GET", "/api/admin/associations/{association_id}/homeowners"),
        ("GET", "/api/admin/homeowners"),
        ("GET", "/api/admin/committee-members"),
        ("POST", "/api/admin/committee-members"),
        ("PUT", "/api/admin/committee-members/{committee_id}/{user_id}"),
        ("DELETE", "/api/admin/committee-members/{committee_id}/{user_id}"),
        ("DELETE", "/api/admin/committee-members/{member_id}"),
        ("GET", "/api/associations/{association_id}/committee-members"),
        ("GET", "/api/user/committees"),
        ("GET", "/api/board_chat/{pool_type}/{pool_id}"),
        ("POST", "/api/board_chat/{pool_type}/{pool_id}"),
    }
    assert expected <= routes
