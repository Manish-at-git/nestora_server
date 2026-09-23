"""Protected administrative routes for entity CRUD."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.entities.schemas import (
    EntityMutationResponse,
    EntityRequest,
    EntityResponse,
)
from app.modules.entities.service import EntityService


router = APIRouter(
    prefix="/admin/entities",
    tags=["Entities"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)


def serialize_entity(entity, is_onboarded: bool | None = None) -> EntityResponse:
    """Map an entity and its derived onboarding status into the client response shape."""
    return EntityResponse(
        id=entity.id,
        entity_type_id=entity.entity_type_id,
        entity_type_name=entity.entity_type.name if entity.entity_type else None,
        association_id=entity.association_id,
        name=entity.name,
        description=entity.description,
        is_onboarded=(entity.association_id is not None if is_onboarded is None else is_onboarded),
        created_at=entity.created_at,
    )


@router.get("", response_model=ApiResponse[list[EntityResponse]])
async def list_entities(session: AsyncSession = Depends(get_db_session)) -> dict:
    """List active entities for an authorized administrator."""
    entities = await EntityService(session).list()
    return success_response(
        [serialize_entity(entity, is_onboarded) for entity, is_onboarded in entities]
    )


@router.post("", response_model=ApiResponse[EntityResponse], status_code=status.HTTP_201_CREATED)
async def create_entity(
    payload: EntityRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create an entity after authentication, role, and CSRF checks."""
    async with UnitOfWork(session):
        entity = await EntityService(session).create(payload)
    return success_response(serialize_entity(entity))


@router.put("/{entity_id}", response_model=ApiResponse[EntityMutationResponse])
async def update_entity(
    entity_id: str,
    payload: EntityRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Update an entity after authentication, role, and CSRF checks."""
    async with UnitOfWork(session):
        await EntityService(session).update(entity_id, payload)
    return success_response(EntityMutationResponse())


@router.delete("/{entity_id}", response_model=ApiResponse[EntityMutationResponse])
async def delete_entity(
    entity_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Soft-delete an entity after authentication, role, and CSRF checks."""
    async with UnitOfWork(session):
        await EntityService(session).delete(entity_id)
    return success_response(EntityMutationResponse())
