"""Unit and route-contract checks for role-feature permission management."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.permissions.messages import PermissionMessage
from app.modules.permissions.schemas import BulkPermissionRequest, PermissionRequest
from app.modules.permissions.service import PermissionService


def test_permission_requests_reject_negative_sidebar_order() -> None:
    with pytest.raises(ValidationError):
        PermissionRequest(role_id="role-1", feature_id="feature-1", sidebar_order=-1)

    with pytest.raises(ValidationError):
        BulkPermissionRequest(
            permissions=[{"feature_id": "feature-1", "can_view": True, "sidebar_order": -1}]
        )


@pytest.mark.asyncio
async def test_create_restores_a_previously_soft_deleted_permission() -> None:
    session = SimpleNamespace(add=Mock(), flush=AsyncMock())
    service = PermissionService(session)
    archived_permission = SimpleNamespace(is_deleted=True)
    service.repository.role_exists = AsyncMock(return_value=True)
    service.repository.feature_exists = AsyncMock(return_value=True)
    service.repository.find_active = AsyncMock(return_value=None)
    service.repository.find_any = AsyncMock(return_value=archived_permission)
    payload = PermissionRequest(
        role_id="role-1",
        feature_id="feature-1",
        can_view=True,
        sidebar_order=3,
    )

    permission = await service.create(payload)

    assert permission is archived_permission
    assert permission.is_deleted is False
    assert permission.can_view is True
    assert permission.sidebar_order == 3
    session.add.assert_called_once_with(archived_permission)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_bulk_update_keeps_disabled_permissions_soft_deleted() -> None:
    existing_permission = SimpleNamespace(feature_id="feature-1", is_deleted=False)
    result = SimpleNamespace(all=lambda: [existing_permission])
    session = SimpleNamespace(add=Mock(), flush=AsyncMock(), scalars=AsyncMock(return_value=result))
    service = PermissionService(session)
    service.repository.role_exists = AsyncMock(return_value=True)
    service.repository.feature_exists = AsyncMock(return_value=True)
    payload = BulkPermissionRequest(
        permissions=[{"feature_id": "feature-1", "can_view": False}]
    )

    await service.bulk_update("role-1", payload)

    assert existing_permission.is_deleted is True
    session.add.assert_not_called()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_matrix_rejects_unknown_role() -> None:
    service = PermissionService(AsyncMock())
    service.repository.role_exists = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as error:
        await service.matrix("missing-role")

    assert error.value.status_code == 404
    assert error.value.detail == PermissionMessage.ROLE_NOT_FOUND


def test_permission_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}

    assert {
        ("GET", "/api/admin/permissions"),
        ("POST", "/api/admin/permissions"),
        ("PUT", "/api/admin/permissions/{permission_id}"),
        ("DELETE", "/api/admin/permissions/{permission_id}"),
        ("GET", "/api/admin/roles-permissions-summary"),
        ("GET", "/api/admin/roles/{role_id}/permissions-matrix"),
        ("POST", "/api/admin/roles/{role_id}/permissions-bulk"),
    } <= routes
