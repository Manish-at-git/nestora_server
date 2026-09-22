"""Delivery for password-reset links and OTPs using the centralized EmailService."""

import logging
from urllib.parse import urlencode

from app.core.config import Settings
from app.core.email import email_service
from app.core.email_templates import password_reset_link_email

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

    async def send_otp(self, recipient: str, otp: str, user_name: str | None = None) -> dict:
        """Deliver a short-lived OTP using the branded Nestora template via Brevo / SMTP."""
        result = await email_service.send_password_reset_otp(
            to_email=recipient,
            otp=otp,
            expires_in_seconds=self.settings.password_reset_otp_ttl_seconds,
            user_name=user_name,
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
