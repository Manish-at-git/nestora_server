"""Unit and route-contract checks for the feature catalogue."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.features.messages import FeatureMessage
from app.modules.features.schemas import FeatureRequest
from app.modules.features.service import FeatureService


def test_feature_request_normalizes_code_and_url() -> None:
    payload = FeatureRequest(
        name="  Permissions  ",
        code="  ROLE_PERMISSIONS  ",
        url="  /permissions  ",
    )

    assert payload.name == "Permissions"
    assert payload.code == "role_permissions"
    assert payload.url == "/permissions"


def test_feature_request_rejects_invalid_code() -> None:
    with pytest.raises(ValidationError, match="Code can only contain"):
        FeatureRequest(name="Permissions", code="role permissions")


@pytest.mark.asyncio
async def test_feature_validation_rejects_a_parent_cycle() -> None:
    service = FeatureService(AsyncMock())
    service.repository.name_exists = AsyncMock(return_value=False)
    service.repository.code_exists = AsyncMock(return_value=False)
    service.repository.get = AsyncMock(
        return_value=SimpleNamespace(id="parent", parent_id="feature-1")
    )
    payload = FeatureRequest(name="Child", code="child", parent_id="parent")

    with pytest.raises(HTTPException) as error:
        await service._validate(payload, excluding_id="feature-1")

    assert error.value.status_code == 400
    assert error.value.detail == FeatureMessage.PARENT_CYCLE


@pytest.mark.asyncio
async def test_create_keeps_the_client_url_as_the_feature_route() -> None:
    service = FeatureService(AsyncMock())
    service.repository.name_exists = AsyncMock(return_value=False)
    service.repository.code_exists = AsyncMock(return_value=False)
    service.repository.get = AsyncMock(return_value=None)
    payload = FeatureRequest(name="Permissions", code="permissions", url="/permissions")

    feature = await service.create(payload)

    assert feature.code == "permissions"
    assert feature.route == "/permissions"


def test_feature_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}

    assert {
        ("GET", "/api/admin/features"),
        ("POST", "/api/admin/features"),
        ("PUT", "/api/admin/features/{feature_id}"),
        ("DELETE", "/api/admin/features/{feature_id}"),
    } <= routes
