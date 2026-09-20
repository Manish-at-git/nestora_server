"""Delivery for password-reset links and OTPs using the centralized EmailService."""

import logging
from urllib.parse import urlencode

from app.core.config import Settings
from app.core.email import email_service

logger = logging.getLogger("nestora.server.auth")


class PasswordResetNotifier:
    """Send password-reset links and OTP codes through centralized EmailService (Brevo / SMTP / Dev Mode)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, recipient: str, token: str) -> dict:
        """Deliver the raw one-time reset link only by email."""
        reset_url = f"{self.settings.frontend_url.rstrip('/')}/reset-password?{urlencode({'token': token})}"
        subject = "Reset your Nestora password"
        text_content = (
            "A password reset was requested for your Nestora account.\n"
            f"Use this one-time link within {self.settings.password_reset_ttl_minutes} minutes:\n{reset_url}\n\n"
            "If you did not request this, you can safely ignore this email."
        )
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F9F8F6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <div style="max-width: 520px; margin: 40px auto; background-color: #ffffff; border: 1px solid #E5E3DB; border-radius: 20px; overflow: hidden; box-shadow: 0 8px 30px rgba(0,0,0,0.04);">
    <div style="background: linear-gradient(135deg, #1E3629 0%, #2C4C3B 100%); padding: 30px; text-align: center;">
      <h1 style="color: #ffffff; font-family: Georgia, serif; font-size: 26px; margin: 0; font-style: italic;">Nestora</h1>
      <p style="color: rgba(255,255,255,0.7); font-size: 11px; text-transform: uppercase; letter-spacing: 0.2em; margin-top: 6px;">Residential Management</p>
    </div>
    <div style="padding: 32px;">
      <h2 style="font-family: Georgia, serif; font-size: 22px; color: #1C1C1A; margin-top: 0;">Reset your password</h2>
      <p style="font-size: 14px; color: #686864; line-height: 1.6;">
        A password reset was requested for your Nestora account. Click the button below to choose a new password:
      </p>
      <div style="text-align: center; margin: 28px 0;">
        <a href="{reset_url}" style="background-color: #2C4C3B; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 9999px; font-weight: 600; font-size: 14px; display: inline-block;">Reset Password</a>
      </div>
      <p style="font-size: 12px; color: #8C8C88; text-align: center;">This link will expire in {self.settings.password_reset_ttl_minutes} minutes.</p>
    </div>
  </div>
</body>
</html>"""
        result = await email_service.send_email(
            to_email=recipient,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )
        self._log_result(recipient, result)
        return result

    async def send_otp(self, recipient: str, otp: str) -> dict:
        """Deliver a short-lived OTP using the branded Nestora template via Brevo / SMTP."""
        result = await email_service.send_password_reset_otp(
            to_email=recipient,
            otp=otp,
            expires_in_minutes=self.settings.password_reset_ttl_minutes,
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
