"""Idempotently seed financial report permissions, including Super Admin access."""

import asyncio

from app.core.config import get_settings
from app.db.session import close_database, session_factory
from app.seed import (
    grant_super_admin_financial_report_permissions,
    normalize_financial_sidebar_order,
    seed_balance_sheet_feature_and_permissions,
    seed_income_statement_feature_and_permissions,
)


async def main() -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise RuntimeError(
            "Refusing to run the financial permission seed in production. "
            "Apply the reviewed Alembic migration instead."
        )

    try:
        async with session_factory() as session:
            async with session.begin():
                balance_counts = await seed_balance_sheet_feature_and_permissions(session)
                income_counts = await seed_income_statement_feature_and_permissions(session)
                super_admin_counts = await grant_super_admin_financial_report_permissions(
                    session
                )
                await normalize_financial_sidebar_order(session)

        print(
            "Seeded financial statement access: "
            f"Balance Sheet ({balance_counts['features_created']} feature created, "
            f"{balance_counts['permissions_created']} permissions created, "
            f"{balance_counts['permissions_updated']} permissions updated, "
            f"{balance_counts['permissions_disabled']} permissions disabled); "
            f"Income Statement ({income_counts['features_created']} feature created, "
            f"{income_counts['permissions_created']} permissions created, "
            f"{income_counts['permissions_updated']} permissions updated, "
            f"{income_counts['permissions_disabled']} permissions disabled); "
            "Super Admin report access "
            f"({super_admin_counts['features_found']} existing features found, "
            f"{super_admin_counts['permissions_created']} permissions created, "
            f"{super_admin_counts['permissions_updated']} permissions updated)."
        )
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
