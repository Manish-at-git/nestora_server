"""Idempotent, one-time reference data for association entity types."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.entity_types.models import EntityType


ENTITY_TYPE_SEED_DATA: tuple[tuple[str, str], ...] = (
    ("Condominium", "Individually owned units with shared common areas."),
    ("Townhouse", "Attached homes in a planned community."),
    ("Single Family", "Standalone homes in a residential community."),
)


async def seed_entity_types(session: AsyncSession) -> dict[str, int]:
    """Create or reactivate the fixed entity-type catalogue without deleting data."""
    created = 0

    for name, description in ENTITY_TYPE_SEED_DATA:
        entity_type = await session.scalar(
            select(EntityType).where(func.lower(EntityType.name) == name.lower())
        )
        if entity_type is None:
            session.add(
                EntityType(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    is_deleted=False,
                )
            )
            created += 1
            continue

        entity_type.name = name
        entity_type.description = description
        entity_type.is_deleted = False

    await session.flush()
    return {
        "entity_types_created": created,
        "entity_types_existing": len(ENTITY_TYPE_SEED_DATA) - created,
    }
