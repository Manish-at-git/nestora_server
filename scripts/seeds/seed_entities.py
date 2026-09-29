"""Manual runner for sample association entities in local or test environments."""

import asyncio

from app.db.session import close_database, session_factory
from app.seed_data.entities import seed_entities


async def main() -> None:
    try:
        async with session_factory() as session:
            async with session.begin():
                counts = await seed_entities(session)
        print(
            "Seeded sample entities: "
            f"{counts['entities_created']} created and "
            f"{counts['entities_existing']} already present."
        )
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
