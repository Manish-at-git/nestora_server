"""Unit and route-contract checks for entity administration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.entities.messages import EntityMessage
from app.modules.entities.schemas import EntityRequest
from app.modules.entities.service import EntityService


def test_entity_request_normalizes_optional_text() -> None:
    payload = EntityRequest(
        entity_type_id="  type-1  ",
        association_id="   ",
        name="  Nestora  ",
        description="  Management entity  ",
    )

    assert payload.entity_type_id == "type-1"
    assert payload.association_id is None
    assert payload.name == "Nestora"
    assert payload.description == "Management entity"


@pytest.mark.parametrize("field", ["entity_type_id", "name"])
def test_entity_request_rejects_required_whitespace(field: str) -> None:
    values = {"entity_type_id": "type-1", "name": "Nestora"}
    values[field] = "   "

    with pytest.raises(ValidationError):
        EntityRequest(**values)


@pytest.mark.asyncio
async def test_create_rejects_duplicate_name_within_entity_type() -> None:
    service = EntityService(AsyncMock())
    service.repository.name_exists = AsyncMock(return_value=True)
    payload = EntityRequest(entity_type_id="type-1", name="Nestora")

    with pytest.raises(HTTPException) as error:
        await service.create(payload)

    assert error.value.status_code == 400
    assert error.value.detail == EntityMessage.NAME_EXISTS
    service.repository.name_exists.assert_awaited_once_with("Nestora", "type-1")


@pytest.mark.asyncio
async def test_delete_uses_soft_delete_for_an_existing_entity() -> None:
    service = EntityService(AsyncMock())
    entity = SimpleNamespace(id="entity-1")
    service.repository.get = AsyncMock(return_value=entity)
    service.repository.soft_delete = AsyncMock()

    await service.delete(entity.id)

    service.repository.soft_delete.assert_awaited_once_with(entity)


def test_entity_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}

    assert {
        ("GET", "/api/admin/entities"),
        ("POST", "/api/admin/entities"),
        ("PUT", "/api/admin/entities/{entity_id}"),
        ("DELETE", "/api/admin/entities/{entity_id}"),
    } <= routes
