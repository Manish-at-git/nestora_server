"""Authentication table models; no plaintext passwords, sessions, or reset tokens are stored."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.iam.models import Role


class Account(Base):
    """Login identity with one normalized email, password hash, status, and role."""

    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("status IN ('active', 'inactive', 'suspended')", name="ck_accounts_status"),)

    # Keep the clean Python attribute ``id`` while using the legacy-compatible
    # database column name required by domain-table foreign keys.
    id: Mapped[str] = mapped_column(
        "account_id", CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    employee_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("employees.employee_id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("user_details.user_id", ondelete="CASCADE"), nullable=True, index=True
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("roles.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    role = relationship(Role)
    sessions = relationship("AuthSession", back_populates="account", cascade="all, delete-orphan")


class AuthSession(Base):
    """A revocable server-side session; only hashes of browser bearer values are persisted."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account", back_populates="sessions")


class PasswordResetChallenge(Base):
    """One-time hashed password-reset challenge; attempts remain available for future short-code delivery."""

    __tablename__ = "password_reset_challenges"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    account = relationship("Account")
