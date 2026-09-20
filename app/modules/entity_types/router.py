"""Protected administrative routes for entity type CRUD."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.entity_types.schemas import (
    EntityTypeMutationResponse,
    EntityTypeRequest,
    EntityTypeResponse,
)
from app.modules.entity_types.service import EntityTypeService


router = APIRouter(
    prefix="/admin/entity-types",
    tags=["Entity Types"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)


@router.get("", response_model=ApiResponse[list[EntityTypeResponse]])
async def list_entity_types(session: AsyncSession = Depends(get_db_session)) -> dict:
    """List classifications for an authorized administrator."""
    entity_types = await EntityTypeService(session).list()
    return success_response([EntityTypeResponse.model_validate(item) for item in entity_types])


@router.post(
    "", response_model=ApiResponse[EntityTypeResponse], status_code=status.HTTP_201_CREATED
)
async def create_entity_type(
    payload: EntityTypeRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create a classification after authentication, role, and CSRF checks."""
    async with UnitOfWork(session):
        entity_type = await EntityTypeService(session).create(payload)
    return success_response(EntityTypeResponse.model_validate(entity_type))


@router.put("/{entity_type_id}", response_model=ApiResponse[EntityTypeMutationResponse])
async def update_entity_type(
    entity_type_id: str,
    payload: EntityTypeRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Update a classification after authentication, role, and CSRF checks."""
    async with UnitOfWork(session):
        await EntityTypeService(session).update(entity_type_id, payload)
    return success_response(EntityTypeMutationResponse())


@router.delete("/{entity_type_id}", response_model=ApiResponse[EntityTypeMutationResponse])
async def delete_entity_type(
    entity_type_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Delete a classification after authentication, role, and CSRF checks."""
    async with UnitOfWork(session):
        await EntityTypeService(session).delete(entity_type_id)
    return success_response(EntityTypeMutationResponse())
