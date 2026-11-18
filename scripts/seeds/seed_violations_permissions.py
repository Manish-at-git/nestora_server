"""Idempotently seed the Violations feature for every resident and reviewer role."""

import asyncio

from app.core.config import get_settings
from app.db.session import close_database, session_factory
from app.seed import seed_violations_feature_and_permissions


async def main() -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise RuntimeError(
            "Refusing to run the violations permission seed in production. "
            "Apply the reviewed release procedure instead."
        )

    try:
        async with session_factory() as session:
            async with session.begin():
                counts = await seed_violations_feature_and_permissions(session)
        print(f"Seeded Violations access: {counts['features_created']} feature created.")
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
