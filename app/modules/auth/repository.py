"""Database queries for authentication; this module never owns a commit or rollback."""

from datetime import datetime

from sqlalchemy import Select, update, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import Account, AuthSession, PasswordResetChallenge
from app.modules.iam.models import Feature, Role, RoleFeaturePermission


class AuthRepository:
    """Small data-access layer for account and session reads and writes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_account_by_email(self, email: str) -> Account | None:
        """Load one account and its role for login without selecting password-like extras."""
        statement: Select[tuple[Account]] = (
            select(Account).options(selectinload(Account.role)).where(Account.email == email)
        )
        return await self.session.scalar(statement)

    async def get_active_session(self, token_hash: str, now: datetime) -> AuthSession | None:
        """Load a valid session plus account and role in one bounded query path."""
        statement: Select[tuple[AuthSession]] = (
            select(AuthSession)
            .options(selectinload(AuthSession.account).selectinload(Account.role))
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        )
        return await self.session.scalar(statement)

    async def get_role_by_code(self, code: str) -> Role | None:
        """Load one active role before creating an account with that role."""
        return await self.session.scalar(
            select(Role).where(
                Role.code == code,
                Role.is_active.is_(True),
                Role.is_deleted.is_(False),
            )
        )

    async def get_role_permissions(self, role_id: str) -> list[tuple[RoleFeaturePermission, Feature]]:
        """Load a role's active feature permissions in one joined query, ordered for navigation."""
        statement = (
            select(RoleFeaturePermission, Feature)
            .join(Feature, RoleFeaturePermission.feature_id == Feature.id)
            .where(
                RoleFeaturePermission.role_id == role_id,
                RoleFeaturePermission.is_deleted.is_(False),
                Feature.is_active.is_(True),
                Feature.is_deleted.is_(False),
                (
                    RoleFeaturePermission.can_create.is_(True)
                    | RoleFeaturePermission.can_view.is_(True)
                    | RoleFeaturePermission.can_update.is_(True)
                    | RoleFeaturePermission.can_delete.is_(True)
                ),
            )
            .order_by(RoleFeaturePermission.sidebar_order, Feature.name)
        )
        return list((await self.session.execute(statement)).tuples())

    async def get_active_password_reset_challenge(
        self, token_hash: str, now: datetime
    ) -> PasswordResetChallenge | None:
        """Load one valid reset challenge together with the account whose password may change."""
        statement: Select[tuple[PasswordResetChallenge]] = (
            select(PasswordResetChallenge)
            .options(selectinload(PasswordResetChallenge.account).selectinload(Account.role))
            .where(
                PasswordResetChallenge.token_hash == token_hash,
                PasswordResetChallenge.consumed_at.is_(None),
                PasswordResetChallenge.expires_at > now,
                PasswordResetChallenge.is_deleted.is_(False),
            )
        )
        return await self.session.scalar(statement)

    def add_session(self, auth_session: AuthSession) -> None:
        """Stage a new session for the surrounding Unit of Work to commit atomically."""
        self.session.add(auth_session)

    def add_account(self, account: Account) -> None:
        """Stage an account for the caller's explicit transaction to commit."""
        self.session.add(account)

    def add_password_reset_challenge(self, challenge: PasswordResetChallenge) -> None:
        """Stage a one-time reset challenge without retaining its raw bearer token."""
        self.session.add(challenge)

    async def revoke_session(self, auth_session: AuthSession, now: datetime) -> None:
        """Mark a session revoked instead of deleting audit-relevant history."""
        auth_session.revoked_at = now
        await self.session.flush()

    async def revoke_all_sessions_for_account(self, account_id: str, now: datetime) -> None:
        """Invalidate every login after a password change so stolen sessions cannot survive it."""
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.account_id == account_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    async def consume_active_reset_challenges_for_account(self, account_id: str, now: datetime) -> None:
        """Invalidate old reset links when issuing or completing a newer reset request."""
        await self.session.execute(
            update(PasswordResetChallenge)
            .where(
                PasswordResetChallenge.account_id == account_id,
                PasswordResetChallenge.consumed_at.is_(None),
                PasswordResetChallenge.is_deleted.is_(False),
            )
            .values(consumed_at=now)
        )
