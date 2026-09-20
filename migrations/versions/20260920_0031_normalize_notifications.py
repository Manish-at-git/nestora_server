"""Normalize notification content and recipient-specific inbox state.

Legacy notifications stored the same title and message once for every account.
This migration preserves every historical notification as a one-recipient
notification, while new broadcasts can share one notification payload.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260920_0031"
down_revision = "20260920_0030"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _create_notifications_table() -> None:
    if "notifications" in _table_names():
        return
    op.create_table(
        "notifications",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("association_id", sa.CHAR(36), nullable=True),
        sa.Column("created_by_account_id", sa.CHAR(36), nullable=True),
        sa.Column("type", sa.String(64), nullable=False, server_default="system"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.CHAR(36), nullable=True),
        sa.Column("action_url", sa.String(255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["associations.id"],
            name="fk_notifications_association",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_account_id"],
            ["accounts.account_id"],
            name="fk_notifications_created_by_account",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def _create_recipients_table() -> None:
    if "notification_recipients" in _table_names():
        return
    op.create_table(
        "notification_recipients",
        sa.Column("notification_id", sa.CHAR(36), nullable=False),
        sa.Column("account_id", sa.CHAR(36), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            name="fk_notification_recipients_notification",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.account_id"],
            name="fk_notification_recipients_account",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notification_id", "account_id"),
    )
    op.create_index(
        "ix_notification_recipients_account_inbox",
        "notification_recipients",
        ["account_id", "archived_at", "read_at", "notification_id"],
    )


def _migrate_legacy_rows() -> None:
    if "notifications_legacy" not in _table_names():
        return

    op.execute(
        """
        INSERT INTO notifications (id, type, title, message, created_at)
        SELECT legacy.id, 'system', legacy.title, legacy.message, legacy.created_at
        FROM notifications_legacy AS legacy
        WHERE NOT EXISTS (
            SELECT 1 FROM notifications AS current WHERE current.id = legacy.id
        )
        """
    )
    op.execute(
        """
        INSERT INTO notification_recipients
            (notification_id, account_id, read_at, delivered_at, created_at)
        SELECT
            legacy.id,
            legacy.account_id,
            CASE WHEN legacy.is_read = 1 THEN legacy.created_at ELSE NULL END,
            legacy.created_at,
            legacy.created_at
        FROM notifications_legacy AS legacy
        WHERE NOT EXISTS (
            SELECT 1
            FROM notification_recipients AS recipient
            WHERE recipient.notification_id = legacy.id
              AND recipient.account_id = legacy.account_id
        )
        """
    )


def upgrade() -> None:
    """Create normalized tables and retain legacy rows as a migration backup."""
    tables = _table_names()
    if "notifications" in tables and "account_id" in _columns("notifications"):
        if "notifications_legacy" not in tables:
            op.rename_table("notifications", "notifications_legacy")

    _create_notifications_table()
    _create_recipients_table()
    _migrate_legacy_rows()


def downgrade() -> None:
    """Restore the legacy table shape when no post-migration rows exist."""
    raise NotImplementedError(
        "Notification normalization is intentionally forward-only. Restore from "
        "notifications_legacy only after confirming no new normalized rows exist."
    )
