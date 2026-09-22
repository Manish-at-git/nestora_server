"""
==============================================================================
Nestora Centralized Email Service (server/app/core/email.py)
==============================================================================
Centralizes email dispatching, HTML template generation, Brevo REST API calls,
SMTP fallbacks, and delivery logging across the entire Nestora server application.
Works like app.core.realtime for WebSockets.
"""

import asyncio
import json
import logging
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any

from app.core.config import Settings, get_settings
from app.core.email_templates import password_reset_otp_email

logger = logging.getLogger("nestora.server.email")

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _send_brevo_sync(
    api_key: str,
    sender_email: str,
    sender_name: str,
    to_email: str,
    to_name: str | None,
    subject: str,
    html_content: str,
    text_content: str | None = None,
) -> dict[str, Any]:
    """Synchronous worker that posts transactional email payload to Brevo API via standard urllib."""
    payload: dict[str, Any] = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [
            {
                "email": to_email,
                "name": to_name or to_email.split("@")[0],
            }
        ],
        "subject": subject,
        "htmlContent": html_content,
    }
    if text_content:
        payload["textContent"] = text_content

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BREVO_API_URL,
        data=data,
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            message_id = parsed.get("messageId", "sent")
            logger.info(f"[BREVO EMAIL SENT] to={to_email} subject='{subject}' messageId={message_id}")
            return {"ok": True, "provider": "brevo", "message_id": message_id}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else str(e)
        logger.error(f"[BREVO API ERROR] HTTP {e.code}: {err_body}")
        return {"ok": False, "provider": "brevo", "status_code": e.code, "error": err_body}
    except Exception as e:
        logger.error(f"[BREVO REQUEST ERROR] {e}")
        return {"ok": False, "provider": "brevo", "error": str(e)}


def _send_smtp_sync(
    settings: Settings,
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str | None = None,
) -> dict[str, Any]:
    """Fallback standard library SMTP delivery when SMTP settings are configured."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email

    if text_content:
        msg.set_content(text_content)
        msg.add_alternative(html_content, subtype="html")
    else:
        msg.set_content(html_content, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)

    logger.info(f"[SMTP EMAIL SENT] to={to_email} subject='{subject}'")
    return {"ok": True, "provider": "smtp"}


class EmailService:
    """
    Centralized email delivery engine for Nestora.
    Manages Brevo REST API, SMTP fallback, HTML templates, and dev mode logging.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
        to_name: str | None = None,
        sender_email: str | None = None,
        sender_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Sends an email using Brevo (preferred), SMTP (secondary),
        or dev logging if unconfigured.
        """
        st = self.settings

        # 1. Brevo REST API
        if st.brevo_api_key:
            effective_sender_email = (
                sender_email
                or st.brevo_sender_email
                or st.smtp_from_email
                or "noreply@nestora.io"
            )
            effective_sender_name = sender_name or st.brevo_sender_name or "Nestora"

            return await asyncio.to_thread(
                _send_brevo_sync,
                st.brevo_api_key,
                effective_sender_email,
                effective_sender_name,
                to_email,
                to_name,
                subject,
                html_content,
                text_content,
            )

        # 2. Standard SMTP fallback
        if st.smtp_host and st.smtp_from_email:
            try:
                return await asyncio.to_thread(
                    _send_smtp_sync,
                    st,
                    to_email,
                    subject,
                    html_content,
                    text_content,
                )
            except Exception as e:
                logger.error(f"[SMTP ERROR] Failed sending to {to_email}: {e}")
                return {"ok": False, "provider": "smtp", "error": str(e)}

        # 3. Development simulation mode
        logger.warning(
            f"[EMAIL SERVICE - DEV MODE] Neither BREVO_API_KEY nor SMTP is configured. "
            f"Simulated email to: {to_email} | Subject: {subject}"
        )
        if text_content:
            logger.info(f"[DEV EMAIL CONTENT]\n{text_content}")

        return {
            "ok": True,
            "provider": "dev_mode",
            "message": "Simulated in console (configure BREVO_API_KEY in server/.env for live delivery)",
        }

    async def send_password_reset_otp(
        self,
        to_email: str,
        otp: str,
        expires_in_seconds: int = 60,
        user_name: str | None = None,
    ) -> dict[str, Any]:
        rendered = password_reset_otp_email(
            name=user_name or to_email.split("@")[0],
            otp=otp,
            expires_in_seconds=expires_in_seconds,
        )
        return await self.send_email(
            to_email=to_email,
            subject=rendered.subject,
            html_content=rendered.html,
            text_content=rendered.text,
            to_name=user_name or to_email.split("@")[0],
        )


# Centralized singleton instance
email_service = EmailService()
