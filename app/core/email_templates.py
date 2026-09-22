"""Reusable branded email templates used by delivery and design-system previews."""

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


def _layout(title: str, content: str) -> str:
    safe_title = escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <style>
    body {{ margin: 0; padding: 0; background: #F9F8F6; color: #1C1C1A; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
    .wrapper {{ width: 100%; background: #F9F8F6; padding: 40px 16px; }}
    .container {{ max-width: 520px; margin: 0 auto; background: #FFFFFF; border: 1px solid #E5E3DB; border-radius: 24px; overflow: hidden; box-shadow: 0 12px 36px rgba(0, 0, 0, 0.04); }}
    .header {{ background: linear-gradient(135deg, #1E3629 0%, #2C4C3B 100%); padding: 36px 32px 30px; text-align: center; }}
    .brand {{ color: #FFFFFF; font-family: Georgia, serif; font-size: 28px; font-style: italic; font-weight: 700; letter-spacing: -0.02em; margin: 0 0 6px; }}
    .brand-subtitle {{ color: rgba(255, 255, 255, 0.7); font-size: 11px; text-transform: uppercase; letter-spacing: 0.25em; margin: 0; }}
    .content {{ padding: 36px 32px; }}
    .heading {{ font-family: Georgia, serif; font-size: 24px; font-weight: 600; color: #1C1C1A; margin: 0 0 12px; }}
    .subtext {{ font-size: 14px; line-height: 1.6; color: #686864; margin: 0 0 28px; }}
    .code-box {{ background: #F4F6F4; border: 1.5px dashed #2C4C3B; border-radius: 16px; padding: 24px; text-align: center; margin: 0 0 28px; }}
    .code {{ font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 700; letter-spacing: 7px; color: #2C4C3B; margin: 0; padding-left: 7px; }}
    .code-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.2em; color: #686864; margin-top: 8px; }}
    .button {{ display: inline-block; background: #2C4C3B; color: #FFFFFF !important; text-decoration: none; padding: 13px 28px; border-radius: 999px; font-weight: 600; font-size: 14px; }}
    .center {{ text-align: center; margin: 28px 0; }}
    .notice {{ background: #FAF9F7; border: 1px solid #EAE8E1; border-radius: 12px; padding: 14px 16px; font-size: 12px; color: #686864; line-height: 1.5; }}
    .expiry {{ font-size: 13px; color: #C05A46; font-weight: 500; text-align: center; margin: 0 0 24px; }}
    .footer {{ padding: 24px 32px; border-top: 1px solid #E5E3DB; background: #FAFAF8; text-align: center; font-size: 11px; color: #8C8C88; line-height: 1.5; }}
  </style>
</head>
<body><div class="wrapper"><div class="container">
  <div class="header"><div class="brand">Nestora</div><p class="brand-subtitle">Residential Management &amp; Governance</p></div>
  {content}
  <div class="footer">&copy; Nestora Platform. All rights reserved.<br>A secure membership and residential community operating system.</div>
</div></div></body>
</html>"""


def registration_code_email(
    *, name: str, registration_code: str, association_name: str
) -> RenderedEmail:
    subject = f"Your {association_name} Nestora registration code"
    safe_name = escape(name or "Resident")
    safe_association = escape(association_name)
    safe_code = escape(registration_code)
    html = _layout(
        subject,
        f"""<div class="content">
  <h1 class="heading">Welcome to {safe_association}</h1>
  <p class="subtext">Hello {safe_name},<br>Your residential community account is ready. Use the registration code below to verify your details and create your Nestora password.</p>
  <div class="code-box"><div class="code">{safe_code}</div><div class="code-label">Registration Code</div></div>
  <div class="notice"><strong>Keep this code private.</strong> Nestora will use it to connect your account with your community membership.</div>
</div>""",
    )
    text = (
        f"Hello {name or 'Resident'},\n\nYour {association_name} Nestora account is ready.\n"
        f"Registration code: {registration_code}\n\n"
        "Use this code to verify your details and create your Nestora password.\n"
        "Keep this code private.\n\n— Nestora Platform\n"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def password_reset_link_email(
    *, name: str, reset_url: str, expires_in_minutes: int
) -> RenderedEmail:
    subject = "Reset your Nestora password"
    safe_name = escape(name or "there")
    safe_url = escape(reset_url, quote=True)
    html = _layout(
        subject,
        f"""<div class="content">
  <h1 class="heading">Reset your password</h1>
  <p class="subtext">Hello {safe_name},<br>We received a request to reset the password for your Nestora account.</p>
  <div class="center"><a class="button" href="{safe_url}">Reset Password</a></div>
  <p class="expiry">This link expires in {expires_in_minutes} minutes.</p>
  <div class="notice"><strong>Security Notice:</strong> If you did not request a password reset, you can safely ignore this email.</div>
</div>""",
    )
    text = (
        "A password reset was requested for your Nestora account.\n"
        f"Use this one-time link within {expires_in_minutes} minutes:\n{reset_url}\n\n"
        "If you did not request this, you can safely ignore this email."
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def password_reset_otp_email(
    *, name: str, otp: str, expires_in_seconds: int
) -> RenderedEmail:
    subject = "Nestora verification code"
    safe_name = escape(name or "there")
    safe_otp = escape(otp)
    html = _layout(
        subject,
        f"""<div class="content">
  <h1 class="heading">Reset your password</h1>
  <p class="subtext">Hello {safe_name},<br>We received a request to reset the password for your Nestora account. Enter the verification code below.</p>
  <div class="code-box"><div class="code">{safe_otp}</div><div class="code-label">One-Time Verification Code</div></div>
  <p class="expiry">This code expires in {expires_in_seconds} seconds.</p>
  <div class="notice"><strong>Security Notice:</strong> If you did not request a password reset, you can safely ignore this email.</div>
</div>""",
    )
    text = (
        f"Hello {name or 'there'},\n"
        "Enter the verification code below to continue resetting your Nestora password.\n\n"
        f"{otp}\nONE-TIME VERIFICATION CODE\n\n"
        f"This code expires in {expires_in_seconds} seconds.\n\n"
        "Security Notice: If you did not request a password reset, you can safely ignore this email."
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def sample_email_templates() -> dict[str, dict[str, str]]:
    """Return safe sample renderings for the public design-system preview."""
    return {
        "registration": registration_code_email(
            name="Aarav Sharma", registration_code="N8K4P2QZ", association_name="Maple Residency"
        ).__dict__,
        "password_reset": password_reset_link_email(
            name="Aarav Sharma",
            reset_url="https://app.nestora.io/reset-password?token=sample-reset-token",
            expires_in_minutes=30,
        ).__dict__,
        "password_reset_otp": password_reset_otp_email(
            name="Aarav Sharma", otp="482913", expires_in_seconds=60
        ).__dict__,
    }
