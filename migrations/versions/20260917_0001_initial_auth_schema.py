"""Create the clean, auth-only Nestora schema for a new database.

This migration must be reviewed and run only against a new database. It does
not alter, copy, or inspect any legacy Nestora table.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260917_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create roles, accounts, revocable sessions, and future password-reset challenges."""
    op.create_table(
        "roles",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )

    op.create_table(
        "accounts",
        sa.Column("account_id", sa.CHAR(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.CHAR(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive', 'suspended')", name="ck_accounts_status"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_accounts_role", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("account_id", name="pk_accounts"),
        sa.UniqueConstraint("email", name="uq_accounts_email"),
    )
    op.create_index("ix_accounts_role_id", "accounts", ["role_id"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("account_id", sa.CHAR(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.account_id"], name="fk_auth_sessions_account", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_sessions_account_id", "auth_sessions", ["account_id"], unique=False)
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"], unique=False)

    op.create_table(
        "password_reset_challenges",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("account_id", sa.CHAR(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.account_id"],
            name="fk_password_reset_challenges_account",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_challenges"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_challenges_token_hash"),
    )
    op.create_index(
        "ix_password_reset_challenges_account_id", "password_reset_challenges", ["account_id"], unique=False
    )
    op.create_index(
        "ix_password_reset_challenges_expires_at", "password_reset_challenges", ["expires_at"], unique=False
    )


def downgrade() -> None:
    """Drop only the new auth database tables in reverse foreign-key order."""
    op.drop_index("ix_password_reset_challenges_expires_at", table_name="password_reset_challenges")
    op.drop_index("ix_password_reset_challenges_account_id", table_name="password_reset_challenges")
    op.drop_table("password_reset_challenges")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_account_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_accounts_role_id", table_name="accounts")
    op.drop_table("accounts")
    op.drop_table("roles")
