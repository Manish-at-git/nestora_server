"""Unit and route-contract checks for entity type administration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.entity_types.messages import EntityTypeMessage
from app.modules.entity_types.schemas import EntityTypeRequest
from app.modules.entity_types.service import EntityTypeService


def test_entity_type_request_normalizes_input() -> None:
    payload = EntityTypeRequest(name="  Homeowners Association  ", description="  Community  ")

    assert payload.name == "Homeowners Association"
    assert payload.description == "Community"


def test_entity_type_request_rejects_blank_name() -> None:
    with pytest.raises(ValidationError, match="Name is required"):
        EntityTypeRequest(name="   ")


@pytest.mark.asyncio
async def test_create_rejects_duplicate_entity_type_name() -> None:
    service = EntityTypeService(AsyncMock())
    service.repository.name_exists = AsyncMock(return_value=True)

    with pytest.raises(HTTPException) as error:
        await service.create(EntityTypeRequest(name="Association"))

    assert error.value.status_code == 400
    assert error.value.detail == EntityTypeMessage.NAME_EXISTS


@pytest.mark.asyncio
async def test_update_rejects_unknown_entity_type() -> None:
    service = EntityTypeService(AsyncMock())
    service.repository.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.update("missing", EntityTypeRequest(name="Association"))

    assert error.value.status_code == 404
    assert error.value.detail == EntityTypeMessage.NOT_FOUND


@pytest.mark.asyncio
async def test_delete_delegates_to_the_soft_delete_repository_method() -> None:
    service = EntityTypeService(AsyncMock())
    entity_type = SimpleNamespace(id="entity-type-1")
    service.repository.get = AsyncMock(return_value=entity_type)
    service.repository.delete = AsyncMock()

    await service.delete(entity_type.id)

    service.repository.delete.assert_awaited_once_with(entity_type)


def test_entity_type_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}

    assert {
        ("GET", "/api/admin/entity-types"),
        ("POST", "/api/admin/entity-types"),
        ("PUT", "/api/admin/entity-types/{entity_type_id}"),
        ("DELETE", "/api/admin/entity-types/{entity_type_id}"),
    } <= routes
