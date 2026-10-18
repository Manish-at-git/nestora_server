"""Idempotently seed the standalone Income Statement feature and role permissions."""

import asyncio

from app.db.session import close_database, session_factory
from app.seed import seed_income_statement_feature_and_permissions


async def main() -> None:
    try:
        async with session_factory() as session:
            async with session.begin():
                counts = await seed_income_statement_feature_and_permissions(session)
        print(
            "Seeded Income Statement access: "
            f"{counts['features_created']} feature created, "
            f"{counts['permissions_created']} permissions created, "
            f"{counts['permissions_updated']} permissions updated, and "
            f"{counts['permissions_disabled']} permissions disabled."
        )
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
