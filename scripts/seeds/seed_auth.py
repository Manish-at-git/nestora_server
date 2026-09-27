"""Manual utility that seeds the static RBAC catalogue and bootstrap superadmin."""

import asyncio

from app.core.config import get_settings
from app.db.session import close_database, session_factory
from app.seed import seed_auth_data


async def main() -> None:
    """Run one transaction so roles and the optional initial account are seeded atomically."""
    try:
        async with session_factory() as session:
            async with session.begin():
                await seed_auth_data(session, get_settings())
        print(
            "Seeded roles, features, permissions, the bootstrap superadmin, "
            "and its welcome notification."
        )
    finally:
        # Manual scripts end their event loop immediately, unlike the API lifespan.
        # Dispose pooled aiomysql connections first to prevent loop-closed warnings.
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
