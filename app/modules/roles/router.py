"""Protected administrative routes for role CRUD."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.roles.schemas import RoleMutationResponse, RoleRequest, RoleResponse
from app.modules.roles.service import RoleService


router = APIRouter(
    prefix="/admin/roles",
    tags=["Roles"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)


def serialize_role(role) -> RoleResponse:
    """Map an ORM role and its joined entity into the client response shape."""
    return RoleResponse(
        id=role.id,
        entity_id=role.entity_id,
        name=role.name,
        code=role.code,
        description=role.description,
        is_active=role.is_active,
        created_at=role.created_at,
        entity_name=role.entity.name if role.entity else None,
    )


@router.get("", response_model=ApiResponse[list[RoleResponse]])
async def list_roles(session: AsyncSession = Depends(get_db_session)) -> dict:
    """List active roles for an authorized administrator."""
    roles = await RoleService(session).list()
    return success_response([serialize_role(role) for role in roles])


@router.post("", response_model=ApiResponse[RoleResponse], status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create a role after authentication, role, and CSRF checks."""
    async with UnitOfWork(session):
        role = await RoleService(session).create(payload)
    return success_response(serialize_role(role))


@router.put("/{role_id}", response_model=ApiResponse[RoleMutationResponse])
async def update_role(
    role_id: str,
    payload: RoleRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Update a role after authentication, role, and CSRF checks."""
    async with UnitOfWork(session):
        await RoleService(session).update(role_id, payload)
    return success_response(RoleMutationResponse())


@router.delete("/{role_id}", response_model=ApiResponse[RoleMutationResponse])
async def delete_role(
    role_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Soft-delete a role after authentication, role, and CSRF checks."""
    async with UnitOfWork(session):
        await RoleService(session).delete(role_id)
    return success_response(RoleMutationResponse())
