"""Delivery for password-reset links and OTPs using the centralized EmailService."""

import logging
from urllib.parse import urlencode

from app.core.config import Settings
from app.core.email import email_service
from app.core.email_templates import password_reset_link_email
from app.modules.email_templates.constants import EmailTemplateEventType
from app.modules.email_templates.service import EmailTemplateService
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nestora.server.auth")


class PasswordResetNotifier:
    """Send password-reset links and OTP codes through centralized EmailService (Brevo / SMTP / Dev Mode)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, recipient: str, token: str, user_name: str | None = None) -> dict:
        """Deliver the raw one-time reset link only by email."""
        reset_url = f"{self.settings.frontend_url.rstrip('/')}/reset-password?{urlencode({'token': token})}"
        rendered = password_reset_link_email(
            name=user_name or recipient.split("@")[0],
            reset_url=reset_url,
            expires_in_minutes=self.settings.password_reset_ttl_minutes,
        )
        result = await email_service.send_email(
            to_email=recipient,
            subject=rendered.subject,
            html_content=rendered.html,
            text_content=rendered.text,
        )
        self._log_result(recipient, result)
        return result

    async def send_otp(
        self,
        recipient: str,
        otp: str,
        user_name: str | None = None,
        session: AsyncSession | None = None,
    ) -> dict:
        """Deliver OTP using the active master template, with the branded fallback."""
        rendered = None
        if session is not None:
            try:
                rendered = await EmailTemplateService(session).render_active(
                    EmailTemplateEventType.PASSWORD_RESET_OTP,
                    {
                        "homeowner_name": user_name or recipient.split("@")[0],
                        "otp": otp,
                        "password_reset_expiry_seconds": self.settings.password_reset_otp_ttl_seconds,
                    },
                )
            except Exception as error:
                logger.warning("OTP master template lookup failed; using fallback: %s", error)

        if rendered is None:
            result = await email_service.send_password_reset_otp(
                to_email=recipient,
                otp=otp,
                expires_in_seconds=self.settings.password_reset_otp_ttl_seconds,
                user_name=user_name,
            )
        else:
            subject, html_content = rendered
            result = await email_service.send_email(
                to_email=recipient,
                subject=subject,
                html_content=html_content,
                to_name=user_name or recipient.split("@")[0],
            )
        self._log_result(recipient, result)
        return result

    @staticmethod
    def _log_result(recipient: str, result: dict) -> None:
        """Make password-reset delivery visible without logging reset secrets."""
        provider = result.get("provider", "unknown")
        if result.get("ok"):
            message_id = result.get("message_id")
            logger.info(
                "[PASSWORD RESET EMAIL ACCEPTED] recipient=%s provider=%s message_id=%s",
                recipient,
                provider,
                message_id or "n/a",
            )
        else:
            logger.error(
                "[PASSWORD RESET EMAIL FAILED] recipient=%s provider=%s error=%s",
                recipient,
                provider,
                result.get("error", "unknown email delivery error"),
            )
