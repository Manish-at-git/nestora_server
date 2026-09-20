"""Business rules for entity type CRUD."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.entity_types.messages import EntityTypeMessage
from app.modules.entity_types.models import EntityType
from app.modules.entity_types.repository import EntityTypeRepository
from app.modules.entity_types.schemas import EntityTypeRequest


class EntityTypeService:
    """Coordinate validation, duplicate checks, and persistence for entity types."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = EntityTypeRepository(session)

    async def list(self) -> list[EntityType]:
        """List all entity types for an authorized administrator."""
        return await self.repository.list()

    async def create(self, payload: EntityTypeRequest) -> EntityType:
        """Create one unique entity type."""
        if await self.repository.name_exists(payload.name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=EntityTypeMessage.NAME_EXISTS,
            )

        entity_type = EntityType(
            id=str(uuid.uuid4()),
            name=payload.name,
            description=payload.description,
        )
        self.repository.add(entity_type)
        await self.repository.session.flush()
        # created_at is populated by the database default. Refresh it while the
        # async session is active so response serialization does not trigger a
        # lazy load outside SQLAlchemy's greenlet context.
        await self.repository.session.refresh(entity_type)
        return entity_type

    async def update(self, entity_type_id: str, payload: EntityTypeRequest) -> EntityType:
        """Update one existing entity type while preserving its identifier."""
        entity_type = await self.repository.get(entity_type_id)
        if entity_type is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=EntityTypeMessage.NOT_FOUND,
            )
        if await self.repository.name_exists(payload.name, excluding_id=entity_type_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=EntityTypeMessage.NAME_EXISTS,
            )

        entity_type.name = payload.name
        entity_type.description = payload.description
        await self.repository.session.flush()
        return entity_type

    async def delete(self, entity_type_id: str) -> None:
        """Delete one existing entity type."""
        entity_type = await self.repository.get(entity_type_id)
        if entity_type is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=EntityTypeMessage.NOT_FOUND,
            )
        await self.repository.delete(entity_type)
