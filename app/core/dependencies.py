"""Reusable FastAPI dependencies for current-account, role, and CSRF enforcement."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.constants import CSRF_HEADER_NAME, RoleCode
from app.core.messages import Message
from app.core.security import secrets_match
from app.db.session import get_db_session
from app.modules.auth.models import Account, AuthSession
from app.modules.auth.service import AuthService


@dataclass
class AuthContext:
    """Authenticated request state reused by route handlers and authorization dependencies."""

    account: Account
    session: AuthSession


def get_app_settings() -> Settings:
    """Expose cached configuration through FastAPI's normal dependency system."""
    return get_settings()


async def get_auth_context(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> AuthContext:
    """Resolve the opaque HttpOnly cookie to a current active account."""
    raw_token = request.cookies.get(settings.session_cookie_name)
    auth_session = await AuthService(session, settings).get_authenticated_session(raw_token)
    return AuthContext(account=auth_session.account, session=auth_session)


async def get_current_account(context: AuthContext = Depends(get_auth_context)) -> Account:
    """Convenience dependency for routes that only need the authenticated account."""
    return context.account


async def require_csrf(
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_app_settings),
) -> AuthContext:
    """Require the readable CSRF cookie and matching header for cookie-authenticated writes."""
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=Message.FORBIDDEN)
    if not secrets_match(header_token, context.session.csrf_token_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=Message.FORBIDDEN)
    return context


def require_role(*role_codes: RoleCode):
    """Create a reusable authorization dependency based on immutable role codes."""

    async def role_dependency(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        role = context.account.role
        if not role or role.code not in role_codes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=Message.FORBIDDEN)
        return context

    return role_dependency
