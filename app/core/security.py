"""Password, opaque-session token, CSRF token, and secure-cookie helpers for authentication."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Response

from app.core.config import Settings


def utc_now() -> datetime:
    """Return timezone-aware UTC timestamps for all security expiry calculations."""
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """Store only a bcrypt password hash; raw passwords must never reach the database."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a supplied password against its bcrypt hash safely."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_secret() -> str:
    """Generate a high-entropy value suitable for a cookie token or CSRF token."""
    return secrets.token_urlsafe(48)


def hash_secret(secret: str) -> str:
    """Hash bearer secrets before persistence so a database leak cannot replay them directly."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def secrets_match(provided: str, expected_hash: str) -> bool:
    """Compare a supplied secret to the stored hash using constant-time comparison."""
    return hmac.compare_digest(hash_secret(provided), expected_hash)


def session_expiry(settings: Settings) -> datetime:
    """Calculate the expiry once so cookie and database records use the same lifetime."""
    return utc_now() + timedelta(hours=settings.session_ttl_hours)


def set_auth_cookies(response: Response, session_token: str, csrf_token: str, settings: Settings) -> None:
    """Set the HttpOnly session cookie and readable CSRF cookie after a successful login."""
    common = {
        "max_age": settings.session_ttl_hours * 60 * 60,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "domain": settings.session_cookie_domain,
        "path": "/",
    }
    response.set_cookie(key=settings.session_cookie_name, value=session_token, httponly=True, **common)
    response.set_cookie(key=settings.csrf_cookie_name, value=csrf_token, httponly=False, **common)


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    """Expire both browser cookies after logout without exposing or reusing their values."""
    kwargs = {"domain": settings.session_cookie_domain, "path": "/"}
    response.delete_cookie(key=settings.session_cookie_name, **kwargs)
    response.delete_cookie(key=settings.csrf_cookie_name, **kwargs)
