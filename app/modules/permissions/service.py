"""Permission assignment and role matrix business rules."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select

from app.modules.iam.models import RoleFeaturePermission
from app.modules.permissions.messages import PermissionMessage
from app.modules.permissions.repository import PermissionRepository
from app.modules.permissions.schemas import BulkPermissionRequest, PermissionRequest


class PermissionService:
    def __init__(self, session) -> None:
        self.repository = PermissionRepository(session)

    async def _validate_refs(self, payload: PermissionRequest) -> None:
        if not await self.repository.role_exists(payload.role_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, PermissionMessage.ROLE_NOT_FOUND)
        if not await self.repository.feature_exists(payload.feature_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, PermissionMessage.FEATURE_NOT_FOUND)

    async def list(self):
        return await self.repository.list()

    async def create(self, payload: PermissionRequest) -> RoleFeaturePermission:
        await self._validate_refs(payload)
        if await self.repository.find_active(payload.role_id, payload.feature_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, PermissionMessage.EXISTS)
        permission = await self.repository.find_any(payload.role_id, payload.feature_id)
        if permission is not None:
            for key, value in payload.model_dump().items():
                setattr(permission, key, value)
            permission.is_deleted = False
        else:
            permission = RoleFeaturePermission(id=str(uuid.uuid4()), is_deleted=False, **payload.model_dump())
        self.repository.session.add(permission)
        await self.repository.session.flush()
        return permission

    async def update(self, permission_id: str, payload: PermissionRequest) -> RoleFeaturePermission:
        permission = await self.repository.get(permission_id)
        if permission is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, PermissionMessage.NOT_FOUND)
        await self._validate_refs(payload)
        if await self.repository.find_active(payload.role_id, payload.feature_id, permission_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, PermissionMessage.EXISTS)
        for key, value in payload.model_dump().items():
            setattr(permission, key, value)
        await self.repository.session.flush()
        return permission

    async def delete(self, permission_id: str) -> None:
        permission = await self.repository.get(permission_id)
        if permission is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, PermissionMessage.NOT_FOUND)
        await self.repository.soft_delete(permission)

    async def matrix(self, role_id: str):
        if not await self.repository.role_exists(role_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, PermissionMessage.ROLE_NOT_FOUND)
        return await self.repository.matrix(role_id)

    async def bulk_update(self, role_id: str, payload: BulkPermissionRequest) -> None:
        if not await self.repository.role_exists(role_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, PermissionMessage.ROLE_NOT_FOUND)
        existing = await self.repository.session.scalars(
            select(RoleFeaturePermission).where(
                RoleFeaturePermission.role_id == role_id,
            )
        )
        existing_by_feature = {permission.feature_id: permission for permission in existing.all()}
        for permission in existing_by_feature.values():
            permission.is_deleted = True
        for item in payload.permissions:
            item_payload = PermissionRequest(role_id=role_id, **item.model_dump())
            if not any(
                (
                    item_payload.can_create,
                    item_payload.can_view,
                    item_payload.can_update,
                    item_payload.can_delete,
                )
            ):
                continue
            await self._validate_refs(item_payload)
            permission = existing_by_feature.get(item.feature_id)
            if permission is None:
                permission = RoleFeaturePermission(id=str(uuid.uuid4()), **item_payload.model_dump())
                self.repository.session.add(permission)
            else:
                for key, value in item_payload.model_dump().items():
                    setattr(permission, key, value)
                permission.is_deleted = False
        await self.repository.session.flush()
