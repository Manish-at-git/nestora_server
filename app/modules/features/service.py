"""Business rules for feature catalogue CRUD and soft deletion."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.features.messages import FeatureMessage
from app.modules.features.repository import FeatureRepository
from app.modules.features.schemas import FeatureRequest
from app.modules.iam.models import Feature


class FeatureService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = FeatureRepository(session)

    async def list(self) -> list[Feature]:
        return await self.repository.list()

    async def _validate(self, payload: FeatureRequest, excluding_id: str | None = None) -> None:
        if await self.repository.name_exists(payload.name, excluding_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, FeatureMessage.NAME_EXISTS)
        if await self.repository.code_exists(payload.code, excluding_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, FeatureMessage.CODE_EXISTS)
        if payload.parent_id:
            parent = await self.repository.get(payload.parent_id)
            if parent is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, FeatureMessage.PARENT_NOT_FOUND)
            if excluding_id and await self._is_descendant(parent, excluding_id):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, FeatureMessage.PARENT_CYCLE)

    async def _is_descendant(self, feature: Feature, ancestor_id: str) -> bool:
        current = feature
        seen: set[str] = set()
        while current.parent_id and current.parent_id not in seen:
            if current.parent_id == ancestor_id:
                return True
            seen.add(current.parent_id)
            parent = await self.repository.get(current.parent_id)
            if parent is None:
                break
            current = parent
        return False

    async def create(self, payload: FeatureRequest) -> Feature:
        await self._validate(payload)
        feature = Feature(
            id=str(uuid.uuid4()),
            code=payload.code,
            name=payload.name,
            description=payload.description,
            parent_id=payload.parent_id,
            icon=payload.icon,
            route=payload.url,
            order_index=0,
            is_system=False,
            is_active=payload.is_active,
            is_deleted=False,
        )
        self.repository.add(feature)
        await self.repository.session.flush()
        return await self.repository.get(feature.id) or feature

    async def update(self, feature_id: str, payload: FeatureRequest) -> Feature:
        feature = await self.repository.get(feature_id)
        if feature is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, FeatureMessage.NOT_FOUND)
        await self._validate(payload, excluding_id=feature_id)
        feature.name = payload.name
        feature.code = payload.code
        feature.description = payload.description
        feature.parent_id = payload.parent_id
        feature.icon = payload.icon
        feature.route = payload.url
        feature.is_active = payload.is_active
        await self.repository.session.flush()
        return feature

    async def delete(self, feature_id: str) -> None:
        feature = await self.repository.get(feature_id)
        if feature is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, FeatureMessage.NOT_FOUND)
        await self.repository.soft_delete(feature)
