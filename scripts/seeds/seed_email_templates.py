"""Manual utility to seed the default editable email-template catalogue."""

import asyncio

from app.db.session import close_database, session_factory
from app.seed_data.email_templates import seed_email_templates


async def main() -> None:
    """Run default email-template seeding in one explicit transaction."""
    try:
        async with session_factory() as session:
            async with session.begin():
                counts = await seed_email_templates(session)
        print(
            "Seeded default email templates: "
            f"{counts['created']} created, {counts['restored']} restored, and "
            f"{counts['unchanged']} already present."
        )
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
