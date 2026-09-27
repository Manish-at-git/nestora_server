"""Idempotent reference data for association entity types and onboarding leads."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.entities.models import Entity
from app.modules.entity_types.models import EntityType


ENTITY_TYPE_SEED_DATA: tuple[tuple[str, str], ...] = (
    ("Apartment", "Multi-unit residential building with shared facilities."),
    ("Condominium", "Individually owned units with shared common areas."),
    ("Housing Society", "Residential society with shared management and amenities."),
    ("Gated Community", "Access-controlled residential development."),
    ("Residential Township", "Large planned residential development."),
    ("Row House", "Attached homes arranged in a row."),
    ("Town House", "Attached multi-storey homes in a planned community."),
    ("Villa Community", "Community of villas with shared infrastructure."),
    ("Independent House Community", "Community of standalone houses."),
    ("Plot Society", "Residential plot-owner society."),
)


ENTITY_SEED_DATA: tuple[tuple[str, str, str], ...] = (
    ("Maple Residency", "Apartment", "Urban residential apartment community."),
    ("Orchid Heights", "Condominium", "Premium condominium development."),
    (
        "Greenfield Housing Society",
        "Housing Society",
        "Managed residential society with common facilities.",
    ),
    ("Silver Oak Enclave", "Gated Community", "Secure gated residential development."),
    ("Sunrise Township", "Residential Township", "Planned township with shared amenities."),
    ("Cedar Row Homes", "Row House", "Row-house residential community."),
    ("Willow Town Homes", "Town House", "Planned town-house community."),
    ("Palm Grove Villas", "Villa Community", "Villa community with shared services."),
    (
        "Meadowview Homes",
        "Independent House Community",
        "Community of detached family homes.",
    ),
    ("Evergreen Plot Society", "Plot Society", "Residential plot-owner society."),
)


async def _upsert_entity_type(
    session: AsyncSession, name: str, description: str
) -> tuple[EntityType, bool]:
    entity_type = await session.scalar(
        select(EntityType).where(func.lower(EntityType.name) == name.lower())
    )
    if entity_type is None:
        entity_type = EntityType(id=str(uuid.uuid4()), name=name, description=description)
        session.add(entity_type)
        await session.flush()
        return entity_type, True

    entity_type.name = name
    entity_type.description = description
    entity_type.is_deleted = False
    return entity_type, False


async def _upsert_entity(
    session: AsyncSession,
    entity_type: EntityType,
    name: str,
    description: str,
) -> bool:
    entity = await session.scalar(
        select(Entity).where(
            Entity.entity_type_id == entity_type.id,
            func.lower(Entity.name) == name.lower(),
        )
    )
    if entity is None:
        entity = Entity(
            id=str(uuid.uuid4()),
            entity_type_id=entity_type.id,
            association_code=None,
            name=name,
            description=description,
        )
        session.add(entity)
        await session.flush()
        return True

    entity.name = name
    entity.description = description
    entity.is_deleted = False
    return False


async def seed_entity_reference_data(session: AsyncSession) -> dict[str, int]:
    """Insert or update the reference catalogue without deleting operator-created records."""
    entity_types: dict[str, EntityType] = {}
    entity_types_created = 0
    entities_created = 0

    for name, description in ENTITY_TYPE_SEED_DATA:
        entity_type, was_created = await _upsert_entity_type(session, name, description)
        entity_types[name] = entity_type
        entity_types_created += int(was_created)

    for name, entity_type_name, description in ENTITY_SEED_DATA:
        entity_type = entity_types[entity_type_name]
        entities_created += int(
            await _upsert_entity(session, entity_type, name, description)
        )

    return {
        "entity_types_created": entity_types_created,
        "entity_types_updated": len(ENTITY_TYPE_SEED_DATA) - entity_types_created,
        "entities_created": entities_created,
        "entities_updated": len(ENTITY_SEED_DATA) - entities_created,
    }
