"""Idempotent sample association entities for local and test environments."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.entities.models import Entity
from app.modules.entity_types.models import EntityType


ENTITY_SEED_DATA: tuple[tuple[str, str, str], ...] = (
    ("Maple Residency", "Condominium", "Urban residential apartment community."),
    ("Orchid Heights", "Condominium", "Premium condominium development."),
    ("Greenfield Housing Society", "Single Family", "Managed residential community with common facilities."),
    ("Silver Oak Enclave", "Single Family", "Secure residential community."),
    ("Sunrise Township", "Single Family", "Planned residential community with shared amenities."),
    ("Cedar Row Homes", "Townhouse", "Attached townhouse residential community."),
    ("Willow Town Homes", "Townhouse", "Planned townhouse community."),
    ("Palm Grove Villas", "Single Family", "Single-family villa community with shared services."),
    ("Meadowview Homes", "Single Family", "Community of detached family homes."),
    ("Evergreen Plot Society", "Single Family", "Single-family residential community."),
)


async def seed_entities(session: AsyncSession) -> dict[str, int]:
    """Insert or update every scripted entity without creating entity types.

    Run the entity-type seed first. Entity records remain separately managed so
    production can omit this optional sample-data command.
    """
    entity_types = {
        entity_type.name: entity_type
        for entity_type in (
            await session.scalars(
                select(EntityType).where(EntityType.is_deleted.is_(False))
            )
        ).all()
    }
    required_types = {entity_type_name for _, entity_type_name, _ in ENTITY_SEED_DATA}
    missing_types = sorted(required_types - entity_types.keys())
    if missing_types:
        missing = ", ".join(missing_types)
        raise RuntimeError(
            f"Missing entity types: {missing}. Run python -m scripts.seeds.seed_entity_types first."
        )

    created = 0
    for name, entity_type_name, description in ENTITY_SEED_DATA:
        entity_type = entity_types[entity_type_name]
        entity = await session.scalar(
            select(Entity).where(
                Entity.entity_type_id == entity_type.id,
                func.lower(Entity.name) == name.lower(),
            )
        )
        if entity is None:
            session.add(
                Entity(
                    id=str(uuid.uuid4()),
                    entity_type_id=entity_type.id,
                    association_code=None,
                    name=name,
                    description=description,
                    is_deleted=False,
                )
            )
            created += 1
            continue

        entity.name = name
        entity.description = description
        entity.is_deleted = False

    await session.flush()
    return {
        "entities_created": created,
        "entities_existing": len(ENTITY_SEED_DATA) - created,
    }
