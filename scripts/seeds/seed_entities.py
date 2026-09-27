"""Manual utility to seed entity types and sample onboarding entities."""

import asyncio

from app.db.session import close_database, session_factory
from app.seed_data.entities import seed_entity_reference_data


async def main() -> None:
    """Run entity reference seeding in one transaction when explicitly requested."""
    try:
        async with session_factory() as session:
            async with session.begin():
                counts = await seed_entity_reference_data(session)
        print(
            "Seeded entity reference data: "
            f"{counts['entity_types_created']} entity types created, "
            f"{counts['entity_types_updated']} entity types updated, "
            f"{counts['entities_created']} entities created, and "
            f"{counts['entities_updated']} entities updated."
        )
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
