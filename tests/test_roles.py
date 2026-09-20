"""Unit and route-contract checks for role administration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.roles.messages import RoleMessage
from app.modules.roles.schemas import RoleRequest
from app.modules.roles.service import RoleService


def test_role_request_normalizes_code_and_text() -> None:
    payload = RoleRequest(name="  Board Member  ", code="  BOARD_MEMBER  ", description="   ")

    assert payload.name == "Board Member"
    assert payload.code == "board_member"
    assert payload.description is None


def test_role_request_rejects_unsafe_code() -> None:
    with pytest.raises(ValidationError, match="Code can only contain"):
        RoleRequest(name="Board Member", code="board member")


@pytest.mark.asyncio
async def test_create_rejects_duplicate_role_code() -> None:
    service = RoleService(AsyncMock())
    service.repository.name_exists = AsyncMock(return_value=False)
    service.repository.code_exists = AsyncMock(return_value=True)

    with pytest.raises(HTTPException) as error:
        await service.create(RoleRequest(name="Board Member", code="board_member"))

    assert error.value.status_code == 400
    assert error.value.detail == RoleMessage.CODE_EXISTS


@pytest.mark.asyncio
async def test_delete_blocks_roles_that_are_assigned_to_accounts() -> None:
    service = RoleService(AsyncMock())
    role = SimpleNamespace(id="role-1")
    service.repository.get = AsyncMock(return_value=role)
    service.repository.has_account_assignment = AsyncMock(return_value=True)

    with pytest.raises(HTTPException) as error:
        await service.delete(role.id)

    assert error.value.status_code == 400
    assert error.value.detail == RoleMessage.ASSIGNED_TO_ACCOUNT


def test_role_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}

    assert {
        ("GET", "/api/admin/roles"),
        ("POST", "/api/admin/roles"),
        ("PUT", "/api/admin/roles/{role_id}"),
        ("DELETE", "/api/admin/roles/{role_id}"),
    } <= routes
