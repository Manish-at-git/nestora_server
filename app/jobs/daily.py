"""Orchestrate every job intended to run once per day."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.vehicle_document_reminders import send_due_vehicle_document_reminders


INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def india_today() -> date:
    """Use the product's operating timezone instead of the host-machine timezone."""
    return datetime.now(INDIA_TIMEZONE).date()


async def run_daily_jobs(session: AsyncSession, *, run_date: date | None = None) -> dict[str, int]:
    """Run the daily job suite and return counts suitable for cron logs."""
    target_date = run_date or india_today()
    vehicle_reminders = await send_due_vehicle_document_reminders(
        session,
        reminder_date=target_date,
    )
    return {"vehicle_document_reminders": vehicle_reminders}
