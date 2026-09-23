"""Database access for entities; transaction ownership stays with the service router."""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.associations.models import Association
from app.modules.entities.models import Entity


class EntityRepository:
    """Small query and persistence boundary for entity records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[tuple[Entity, bool]]:
        """Return active entities with their derived onboarding status."""
        statement: Select[tuple[Entity]] = (
            select(Entity)
            .where(Entity.is_deleted.is_(False))
            .order_by(Entity.created_at.desc())
        )
        entities = list((await self.session.scalars(statement)).all())
        onboarded_entity_ids = set(
            await self.session.scalars(
                select(Association.entity_id).where(
                    Association.entity_id.is_not(None),
                    Association.is_deleted.is_(False),
                )
            )
        )
        return [
            (entity, bool(entity.association_id or entity.id in onboarded_entity_ids))
            for entity in entities
        ]

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
