"""Manual, one-time runner for the fixed entity-type catalogue."""

import asyncio

from app.db.session import close_database, session_factory
from app.seed_data.entity_types import seed_entity_types


async def main() -> None:
    try:
        async with session_factory() as session:
            async with session.begin():
                counts = await seed_entity_types(session)
        print(
            "Seeded entity types: "
            f"{counts['entity_types_created']} created and "
            f"{counts['entity_types_existing']} already present."
        )
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
