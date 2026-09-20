"""Database access for entities; transaction ownership stays with the service router."""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.entities.models import Entity


class EntityRepository:
    """Small query and persistence boundary for entity records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Entity]:
        """Return active entities newest first with their entity type loaded."""
        statement: Select[tuple[Entity]] = (
            select(Entity)
            .where(Entity.is_deleted.is_(False))
            .order_by(Entity.created_at.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def get(self, entity_id: str) -> Entity | None:
        """Load one active entity by its stable identifier."""
        statement = select(Entity).where(
            Entity.id == entity_id,
            Entity.is_deleted.is_(False),
        )
        return await self.session.scalar(statement)

    async def name_exists(
        self,
        name: str,
        entity_type_id: str,
        excluding_id: str | None = None,
    ) -> bool:
        """Check active entity names case-insensitively within one entity type."""
        statement = select(Entity.id).where(
            func.lower(Entity.name) == name.lower(),
            Entity.entity_type_id == entity_type_id,
            Entity.is_deleted.is_(False),
        )
        if excluding_id is not None:
            statement = statement.where(Entity.id != excluding_id)
        return await self.session.scalar(statement) is not None

    def add(self, entity: Entity) -> None:
        """Stage a new entity for the surrounding unit of work."""
        self.session.add(entity)

    async def soft_delete(self, entity: Entity) -> None:
        """Mark an entity deleted while retaining its database row."""
        entity.is_deleted = True
        await self.session.flush()
