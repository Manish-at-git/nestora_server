"""Business rules for entity CRUD and soft deletion."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.entities.messages import EntityMessage
from app.modules.entities.models import Entity
from app.modules.entities.repository import EntityRepository
from app.modules.entities.schemas import EntityRequest


class EntityService:
    """Coordinate validation, duplicate checks, and persistence for entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = EntityRepository(session)

    async def list(self) -> list[tuple[Entity, bool]]:
        """List active entities for an authorized administrator."""
        return await self.repository.list()

    async def create(self, payload: EntityRequest) -> Entity:
        """Create one unique active entity within its entity type."""
        if await self.repository.name_exists(payload.name, payload.entity_type_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=EntityMessage.NAME_EXISTS,
            )

        entity = Entity(
            id=str(uuid.uuid4()),
            entity_type_id=payload.entity_type_id,
            association_id=payload.association_id,
            name=payload.name,
            description=payload.description,
        )
        self.repository.add(entity)
        await self.repository.session.flush()
        await self.repository.session.refresh(entity)
        return entity

    async def update(self, entity_id: str, payload: EntityRequest) -> Entity:
        """Update one active entity while preserving its identifier."""
        entity = await self.repository.get(entity_id)
        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=EntityMessage.NOT_FOUND,
            )
        if await self.repository.name_exists(
            payload.name,
            payload.entity_type_id,
            excluding_id=entity_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=EntityMessage.NAME_EXISTS,
            )

        entity.entity_type_id = payload.entity_type_id
        entity.association_id = payload.association_id
        entity.name = payload.name
        entity.description = payload.description
        await self.repository.session.flush()
        return entity

    async def delete(self, entity_id: str) -> None:
        """Soft-delete one active entity."""
        entity = await self.repository.get(entity_id)
        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=EntityMessage.NOT_FOUND,
            )
        await self.repository.soft_delete(entity)
