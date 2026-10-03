"""Add event pass booking, transfer, and gate check-in schema.

Revision ID: 20261003_0037
Revises: 20260927_0036

The legacy event-pass commit created passes and transfers without check-in
storage. Guarding each addition also permits upgrading that partial schema.
"""

import sqlalchemy as sa
from alembic import op


revision = "20261003_0037"
down_revision = "20260927_0036"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if "events" not in _tables():
        raise RuntimeError("The events table must exist before event passes can be added.")

    event_columns = _columns("events")
    if "has_pass" not in event_columns:
        op.add_column("events", sa.Column("has_pass", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    if "pass_price" not in event_columns:
        op.add_column("events", sa.Column("pass_price", sa.Numeric(10, 2), nullable=True))
    if "max_passes_per_user" not in event_columns:
        op.add_column("events", sa.Column("max_passes_per_user", sa.Integer(), nullable=False, server_default="10"))

    if "event_passes" not in _tables():
        op.create_table(
            "event_passes",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("event_id", sa.CHAR(36), nullable=False),
            sa.Column("account_id", sa.CHAR(36), nullable=False),
            sa.Column("buyer_name", sa.String(150)),
            sa.Column("buyer_mobile", sa.String(50)),
            sa.Column("total_passes", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("remaining_passes", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("checked_in_passes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("pass_code", sa.String(50), nullable=False, unique=True),
            sa.Column("qr_data", sa.Text()),
            sa.Column("amount_paid", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
            sa.Column("payment_method", sa.String(50), server_default="wallet"),
            sa.Column("payment_status", sa.String(50), server_default="Completed"),
            sa.Column("status", sa.String(50), server_default="Active"),
            sa.Column("shared_from_pass_id", sa.CHAR(36)),
            sa.Column("shared_to_mobile", sa.String(50)),
            sa.Column("last_checked_in_at", sa.DateTime()),
            sa.Column("last_checked_in_by", sa.CHAR(36)),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["shared_from_pass_id"], ["event_passes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["last_checked_in_by"], ["accounts.account_id"], ondelete="SET NULL"),
        )
        op.create_index("ix_event_passes_event_id", "event_passes", ["event_id"])
        op.create_index("ix_event_passes_account_id", "event_passes", ["account_id"])
        op.create_index("ix_event_passes_buyer_mobile", "event_passes", ["buyer_mobile"])
    else:
        # The source commit did not add these columns, but its check-in routes use them.
        pass_columns = _columns("event_passes")
        if "checked_in_passes" not in pass_columns:
            op.add_column("event_passes", sa.Column("checked_in_passes", sa.Integer(), nullable=False, server_default="0"))
        if "last_checked_in_at" not in pass_columns:
            op.add_column("event_passes", sa.Column("last_checked_in_at", sa.DateTime()))
        if "last_checked_in_by" not in pass_columns:
            op.add_column("event_passes", sa.Column("last_checked_in_by", sa.CHAR(36)))

    if "event_pass_transfers" not in _tables():
        op.create_table(
            "event_pass_transfers",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("original_pass_id", sa.CHAR(36), nullable=False),
            sa.Column("new_pass_id", sa.CHAR(36), nullable=False),
            sa.Column("event_id", sa.CHAR(36), nullable=False),
            sa.Column("sender_account_id", sa.CHAR(36), nullable=False),
            sa.Column("sender_name", sa.String(150)),
            sa.Column("sender_mobile", sa.String(50)),
            sa.Column("recipient_mobile", sa.String(50), nullable=False),
            sa.Column("recipient_name", sa.String(150)),
            sa.Column("count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["original_pass_id"], ["event_passes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["new_pass_id"], ["event_passes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["sender_account_id"], ["accounts.account_id"], ondelete="CASCADE"),
        )
        op.create_index("ix_event_pass_transfers_original_pass_id", "event_pass_transfers", ["original_pass_id"])
        op.create_index("ix_event_pass_transfers_new_pass_id", "event_pass_transfers", ["new_pass_id"])
        op.create_index("ix_event_pass_transfers_event_id", "event_pass_transfers", ["event_id"])

    if "event_pass_checkins" not in _tables():
        op.create_table(
            "event_pass_checkins",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("pass_id", sa.CHAR(36), nullable=False),
            sa.Column("event_id", sa.CHAR(36), nullable=False),
            sa.Column("admitted_count", sa.Integer(), nullable=False),
            sa.Column("checked_in_by", sa.CHAR(36)),
            sa.Column("checked_in_by_name", sa.String(150)),
            sa.Column("notes", sa.Text()),
            sa.Column("checked_in_at", sa.DateTime(), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["pass_id"], ["event_passes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["checked_in_by"], ["accounts.account_id"], ondelete="SET NULL"),
        )
        op.create_index("ix_event_pass_checkins_pass_id", "event_pass_checkins", ["pass_id"])
        op.create_index("ix_event_pass_checkins_event_id", "event_pass_checkins", ["event_id"])


def downgrade() -> None:
    # These tables may contain paid bookings or may have existed before this
    # migration. An automatic downgrade could erase them.
    raise RuntimeError("Event-pass schema requires a reviewed, data-preserving downgrade.")
