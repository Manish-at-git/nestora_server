"""Idempotently create the Staff feature and its operational role permissions."""

import asyncio

from app.core.config import get_settings
from app.db.session import close_database, session_factory
from app.seed import seed_staff_feature_and_permissions


async def main() -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise RuntimeError(
            "Refusing to run the staff permission seed in production. "
            "Apply the reviewed release procedure instead."
        )
    try:
        async with session_factory() as session:
            async with session.begin():
                counts = await seed_staff_feature_and_permissions(session)
        print(
            "Seeded Staff access: "
            f"{counts['features_created']} feature created, "
            f"{counts['permissions_created']} permissions created, "
            f"{counts['permissions_updated']} permissions updated."
        )
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
