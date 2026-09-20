"""Small reusable Fernet wrapper for sensitive domain fields."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _cipher() -> Fernet:
    settings = get_settings()
    configured_key = getattr(settings, "encryption_key", None)
    if configured_key:
        return Fernet(configured_key.encode())

    # Keep local development usable while allowing production to provide a
    # dedicated ENCRYPTION_KEY. The fallback is stable for one database setup.
    digest = hashlib.sha256(
        f"{settings.mysql_password}:{settings.session_cookie_name}".encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_field(value: str | None) -> str | None:
    """Encrypt an optional value before persistence."""
    if not value:
        return None
    return _cipher().encrypt(value.encode()).decode()


def decrypt_field(value: str | None) -> str | None:
    """Decrypt an optional value, returning ``None`` for invalid legacy data."""
    if not value:
        return None
    try:
        return _cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def mask_secret(value: str | None, visible_suffix: int = 4) -> str:
    """Return a safe masked representation for API responses."""
    if not value:
        return "****"
    return f"{'*' * 8}{value[-visible_suffix:]}" if len(value) > visible_suffix else "****"
