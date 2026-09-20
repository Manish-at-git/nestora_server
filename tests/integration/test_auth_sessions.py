"""Opt-in integration tests for session expiry and revocation against a real isolated MySQL database.

Set TEST_DATABASE_URL to an async MySQL URL for a dedicated test database that
has already received this server's Alembic migration.  These tests never use
the development or production database and are skipped when the variable is absent.
"""

import os
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.constants import AccountStatus
from app.core.security import generate_secret, hash_password, hash_secret, utc_now
from app.modules.auth.models import Account, AuthSession, PasswordResetChallenge
from app.modules.auth.service import AuthService
from app.modules.iam.models import Role

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    pytestmark = pytest.mark.skip(reason="TEST_DATABASE_URL is not configured for an isolated MySQL database")
else:
    pytestmark = pytest.mark.integration


@pytest.fixture
async def database_session() -> AsyncSession:
    """Open one real database session only after proving the manually migrated tables exist."""
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        try:
            await session.execute(text("SELECT 1 FROM roles LIMIT 1"))
        except Exception as error:
            await engine.dispose()
            pytest.skip(f"The isolated test database is not migrated: {error}")
        yield session
    await engine.dispose()


async def _create_test_account(session: AsyncSession) -> tuple[Account, str, str, str]:
    """Create isolated rows with UUIDs so teardown can remove only data owned by this test."""
    suffix = uuid.uuid4().hex
    role = Role(id=str(uuid.uuid4()), code=f"test_role_{suffix}", name="Integration test role")
    account = Account(
        id=str(uuid.uuid4()),
        email=f"session-{suffix}@example.test",
        password_hash=hash_password("StrongPassword1!"),
        role_id=role.id,
        role=role,
        status=AccountStatus.ACTIVE,
    )
    raw_token = generate_secret()
    auth_session = AuthSession(
        id=str(uuid.uuid4()),
        account_id=account.id,
        token_hash=hash_secret(raw_token),
        csrf_token_hash=hash_secret(generate_secret()),
        expires_at=utc_now() + timedelta(hours=1),
    )
    session.add_all([role, account, auth_session])
    await session.commit()
    return account, role.id, auth_session.id, raw_token


async def _remove_test_account(session: AsyncSession, account_id: str, role_id: str) -> None:
    """Remove only this test's child rows and parent rows from the isolated test database."""
    await session.execute(delete(PasswordResetChallenge).where(PasswordResetChallenge.account_id == account_id))
    await session.execute(delete(AuthSession).where(AuthSession.account_id == account_id))
    await session.execute(delete(Account).where(Account.id == account_id))
    await session.execute(delete(Role).where(Role.id == role_id))
    await session.commit()


async def test_logout_revokes_a_real_persisted_session(database_session: AsyncSession) -> None:
    """A revoked session must remain unusable after commit, even when its raw cookie value is retained."""
    account, role_id, session_id, raw_token = await _create_test_account(database_session)
    settings = SimpleNamespace(session_ttl_hours=1)
    service = AuthService(database_session, settings)  # type: ignore[arg-type]
    try:
        loaded = await service.get_authenticated_session(raw_token)
        assert loaded.id == session_id
        await service.logout(loaded)
        await database_session.commit()

        with pytest.raises(HTTPException) as raised:
            await service.get_authenticated_session(raw_token)
        assert raised.value.status_code == status.HTTP_401_UNAUTHORIZED
    finally:
        await _remove_test_account(database_session, account.id, role_id)


async def test_expired_real_session_is_rejected(database_session: AsyncSession) -> None:
    """An expired row must fail authentication even before a scheduled cleanup task deletes it."""
    account, role_id, session_id, raw_token = await _create_test_account(database_session)
    settings = SimpleNamespace(session_ttl_hours=1)
    service = AuthService(database_session, settings)  # type: ignore[arg-type]
    try:
        persisted_session = await database_session.get(AuthSession, session_id)
        assert persisted_session is not None
        persisted_session.expires_at = utc_now() - timedelta(seconds=1)
        await database_session.commit()

        with pytest.raises(HTTPException) as raised:
            await service.get_authenticated_session(raw_token)
        assert raised.value.status_code == status.HTTP_401_UNAUTHORIZED
    finally:
        await _remove_test_account(database_session, account.id, role_id)
