"""Business rules for role CRUD and soft deletion."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iam.models import Role
from app.modules.roles.messages import RoleMessage
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleRequest


class RoleService:
    """Coordinate validation, duplicate checks, and persistence for roles."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = RoleRepository(session)

    async def list(self) -> list[Role]:
        """List active roles for an authorized administrator."""
        return await self.repository.list()

    async def create(self, payload: RoleRequest) -> Role:
        """Create one active role with unique name and code."""
        if await self.repository.name_exists(payload.name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=RoleMessage.NAME_EXISTS,
            )
        if await self.repository.code_exists(payload.code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=RoleMessage.CODE_EXISTS,
            )

        role = Role(
            id=str(uuid.uuid4()),
            entity_id=payload.entity_id,
            name=payload.name,
            code=payload.code,
            description=payload.description,
            is_active=payload.is_active,
            is_system=False,
            is_deleted=False,
        )
        self.repository.add(role)
        await self.repository.session.flush()
        loaded_role = await self.repository.get(role.id)
        return loaded_role or role

    async def update(self, role_id: str, payload: RoleRequest) -> Role:
        """Update one active role while preserving its identifier."""
        role = await self.repository.get(role_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=RoleMessage.NOT_FOUND)
        if await self.repository.name_exists(payload.name, excluding_id=role_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=RoleMessage.NAME_EXISTS,
            )
        if await self.repository.code_exists(payload.code, excluding_id=role_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=RoleMessage.CODE_EXISTS,
            )

        role.entity_id = payload.entity_id
        role.name = payload.name
        role.code = payload.code
        role.description = payload.description
        role.is_active = payload.is_active
        await self.repository.session.flush()
        return role

    async def delete(self, role_id: str) -> None:
        """Soft-delete one unassigned active role."""
        role = await self.repository.get(role_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=RoleMessage.NOT_FOUND)
        if await self.repository.has_account_assignment(role_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=RoleMessage.ASSIGNED_TO_ACCOUNT,
            )
        await self.repository.soft_delete(role)
