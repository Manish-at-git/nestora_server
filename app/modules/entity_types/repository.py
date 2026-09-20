"""Database access for entity types; transaction ownership stays with the service router."""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.entity_types.models import EntityType


class EntityTypeRepository:
    """Small query and persistence boundary for entity type records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[EntityType]:
        """Return newest classifications first, matching the legacy administrative view."""
        statement: Select[tuple[EntityType]] = (
            select(EntityType)
            .where(EntityType.is_deleted.is_(False))
            .order_by(EntityType.created_at.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def get(self, entity_type_id: str) -> EntityType | None:
        """Load one active classification by its stable identifier."""
        statement = select(EntityType).where(
            EntityType.id == entity_type_id,
            EntityType.is_deleted.is_(False),
        )
        return await self.session.scalar(statement)

    async def name_exists(self, name: str, excluding_id: str | None = None) -> bool:
        """Check duplicate names case-insensitively without changing the existing schema."""
        statement = select(EntityType.id).where(
            func.lower(EntityType.name) == name.lower(),
            EntityType.is_deleted.is_(False),
        )
        if excluding_id is not None:
            statement = statement.where(EntityType.id != excluding_id)
        return await self.session.scalar(statement) is not None

    def add(self, entity_type: EntityType) -> None:
        """Stage a new classification for the surrounding unit of work."""
        self.session.add(entity_type)

    async def delete(self, entity_type: EntityType) -> None:
        """Mark a classification deleted while retaining its database row."""
        entity_type.is_deleted = True
        await self.session.flush()
