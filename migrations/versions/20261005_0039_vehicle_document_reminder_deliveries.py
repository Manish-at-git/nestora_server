"""Track sent vehicle-document reminders to make scheduled jobs idempotent.

Revision ID: 20261005_0039
Revises: 20261005_0038
"""

import sqlalchemy as sa
from alembic import op


revision = "20261005_0039"
down_revision = "20261005_0038"
branch_labels = None
depends_on = None


TABLE_NAME = "vehicle_document_reminder_deliveries"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE_NAME in inspector.get_table_names():
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("vehicle_id", sa.CHAR(36), nullable=False),
        sa.Column("account_id", sa.CHAR(36), nullable=False),
        sa.Column("document_type", sa.String(20), nullable=False),
        sa.Column("reminder_date", sa.Date(), nullable=False),
        sa.Column("notification_id", sa.CHAR(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "vehicle_id",
            "document_type",
            "reminder_date",
            name="uq_vehicle_document_reminder_delivery",
        ),
    )
    op.create_index(
        "ix_vehicle_document_reminder_deliveries_reminder_date",
        TABLE_NAME,
        ["reminder_date"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return
    op.drop_index("ix_vehicle_document_reminder_deliveries_reminder_date", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
