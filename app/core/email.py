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
        expires_in_minutes: int = 30,
        user_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Builds and sends a premium branded HTML email containing the 6-digit OTP
        for password recovery.
        """
        subject = f"{otp} is your Nestora verification code"
        greeting = user_name or to_email.split("@")[0]

        text_content = (
            f"Hello {greeting},\n\n"
            f"You requested a password reset for your Nestora account.\n\n"
            f"Your verification code is: {otp}\n\n"
            f"This code expires in {expires_in_minutes} minutes.\n\n"
            f"If you did not request this, please safely ignore this email.\n\n"
            f"— Nestora Platform\n"
        )

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #F9F8F6;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #1C1C1A;
      -webkit-font-smoothing: antialiased;
    }}
    .wrapper {{
      width: 100%;
      background-color: #F9F8F6;
      padding: 40px 16px;
    }}
    .container {{
      max-width: 520px;
      margin: 0 auto;
      background-color: #FFFFFF;
      border: 1px solid #E5E3DB;
      border-radius: 24px;
      overflow: hidden;
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.04);
    }}
    .header {{
      background: linear-gradient(135deg, #1E3629 0%, #2C4C3B 100%);
      padding: 36px 32px 30px 32px;
      text-align: center;
    }}
    .brand {{
      color: #FFFFFF;
      font-family: Georgia, serif;
      font-size: 28px;
      font-style: italic;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin: 0 0 6px 0;
    }}
    .brand-subtitle {{
      color: rgba(255, 255, 255, 0.7);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.25em;
      margin: 0;
    }}
    .content {{
      padding: 36px 32px;
    }}
    .heading {{
      font-family: Georgia, serif;
      font-size: 24px;
      font-weight: 600;
      color: #1C1C1A;
      margin: 0 0 12px 0;
    }}
    .subtext {{
      font-size: 14px;
      line-height: 1.6;
      color: #686864;
      margin: 0 0 28px 0;
    }}
    .otp-box {{
      background: #F4F6F4;
      border: 1.5px dashed #2C4C3B;
      border-radius: 16px;
      padding: 24px;
      text-align: center;
      margin: 0 0 28px 0;
    }}
    .otp-code {{
      font-family: 'Courier New', Courier, monospace;
      font-size: 38px;
      font-weight: 700;
      letter-spacing: 8px;
      color: #2C4C3B;
      margin: 0;
      padding-left: 8px;
    }}
    .otp-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.2em;
      color: #686864;
      margin-top: 8px;
    }}
    .expiry-note {{
      font-size: 13px;
      color: #C05A46;
      font-weight: 500;
      text-align: center;
      margin: 0 0 24px 0;
    }}
    .security-notice {{
      background-color: #FAF9F7;
      border: 1px solid #EAE8E1;
      border-radius: 12px;
      padding: 14px 16px;
      font-size: 12px;
      color: #686864;
      line-height: 1.5;
    }}
    .footer {{
      padding: 24px 32px;
      border-top: 1px solid #E5E3DB;
      background-color: #FAFAF8;
      text-align: center;
      font-size: 11px;
      color: #8C8C88;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <div class="brand">Nestora</div>
        <p class="brand-subtitle">Residential Management & Governance</p>
      </div>
      <div class="content">
        <h1 class="heading">Reset your password</h1>
        <p class="subtext">
          Hello {greeting},<br>
          We received a request to reset the password for your Nestora account. Enter the verification code below:
        </p>

        <div class="otp-box">
          <div class="otp-code">{otp}</div>
          <div class="otp-label">One-Time Verification Code</div>
        </div>

        <p class="expiry-note">&#9201; This code expires in {expires_in_minutes} minutes.</p>

        <div class="security-notice">
          <strong>Security Notice:</strong> If you did not request a password reset, you can safely ignore this email. Your account credentials remain secure.
        </div>
      </div>
      <div class="footer">
        &copy; Nestora Platform. All rights reserved.<br>
        A secure membership and residential community operating system.
      </div>
    </div>
  </div>
</body>
</html>"""

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            to_name=greeting,
        )


# Centralized singleton instance
email_service = EmailService()
