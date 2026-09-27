"""Idempotent default email-template reference data."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.email_templates.constants import EmailTemplateEventType
from app.modules.email_templates.models import EmailTemplate


SERVER_TEMPLATE_DIRECTORY = (
    Path(__file__).resolve().parent.parent / "modules" / "email_templates" / "templates"
)


EMAIL_TEMPLATE_SEED_DATA: tuple[tuple[str, str, str, str], ...] = (
    (
        "Welcome New Resident",
        EmailTemplateEventType.WELCOME_HOMEOWNER,
        "Your {association_name} Nestora registration code",
        "onboarding-registration-code.html",
    ),
    (
        "Forgot Password OTP",
        EmailTemplateEventType.PASSWORD_RESET_OTP,
        "Nestora verification code",
        "forgot-password-otp.html",
    ),
)


def load_email_template_html(filename: str) -> str:
    """Read one self-contained HTML template from the server-owned module assets."""
    template_path = SERVER_TEMPLATE_DIRECTORY / filename
    if not template_path.is_file():
        raise FileNotFoundError(f"Email template source is missing: {template_path}")

    body = template_path.read_text(encoding="utf-8").strip()
    if not body:
        raise ValueError(f"Email template source is empty: {template_path}")
    if len(body) > 65535:
        raise ValueError(f"Email template source exceeds the database limit: {template_path}")
    return body

async def _upsert_email_template(
    session: AsyncSession,
    name: str,
    event_type: str,
    subject: str,
    body: str,
) -> str:
    template = await session.scalar(
        select(EmailTemplate).where(func.lower(EmailTemplate.event_type) == event_type.lower())
    )
    if template is None:
        session.add(
            EmailTemplate(
                id=str(uuid.uuid4()),
                name=name,
                event_type=event_type,
                subject=subject,
                body=body,
                is_active=True,
            )
        )
        await session.flush()
        return "created"

    if template.is_deleted:
        template.is_deleted = False
        return "restored"

    return "unchanged"


async def seed_email_templates(session: AsyncSession) -> dict[str, int]:
    """Create missing defaults while preserving existing administrator edits."""
    counts = {"created": 0, "restored": 0, "unchanged": 0}
    for name, event_type, subject, filename in EMAIL_TEMPLATE_SEED_DATA:
        result = await _upsert_email_template(
            session,
            name,
            event_type,
            subject,
            load_email_template_html(filename),
        )
        counts[result] += 1
    return counts
