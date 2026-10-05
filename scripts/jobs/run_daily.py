"""Run the centralized daily Nestora jobs once.

Example cron entry (the deployment scheduler should invoke this command once
per day at 09:00 Asia/Kolkata):

    cd /path/to/server && DEBUG=false ./.venv/bin/python -m scripts.jobs.run_daily
"""

import asyncio

from app.db.session import close_database, session_factory
from app.db.unit_of_work import UnitOfWork
from app.jobs.daily import run_daily_jobs
from app.modules.notifications.service import publish_pending_notifications


async def main() -> None:
    """Commit all daily effects before publishing realtime notifications."""
    try:
        async with session_factory() as session:
            async with UnitOfWork(session):
                result = await run_daily_jobs(session)
            await publish_pending_notifications(session)
        print(f"Daily jobs completed: {result}")
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
