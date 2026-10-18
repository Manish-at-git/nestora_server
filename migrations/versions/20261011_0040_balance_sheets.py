"""Add the original normalized Balance Sheet snapshot tables.

Revision ID: 20261011_0040
Revises: 20261005_0039

This historical revision remains in the chain because deployed databases may
already identify it as their current revision. The following revision upgrades
its columns to the current Balance Sheet contract without dropping data.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261011_0040"
down_revision = "20261005_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "balance_sheets",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("association_id", sa.CHAR(36), nullable=False),
        sa.Column("as_on_date", sa.Date(), nullable=False),
        sa.Column("health_status", sa.String(50)),
        sa.Column("health_note", sa.Text()),
        sa.Column("created_by", sa.CHAR(36)),
        sa.Column("updated_by", sa.CHAR(36)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["associations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["accounts.account_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["accounts.account_id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "association_id",
            "as_on_date",
            name="uq_balance_sheets_association_date",
        ),
    )
    op.create_index(
        "ix_balance_sheets_association_id",
        "balance_sheets",
        ["association_id"],
    )
    op.create_index(
        "ix_balance_sheets_as_on_date",
        "balance_sheets",
        ["as_on_date"],
    )
    op.create_table(
        "balance_sheet_items",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("balance_sheet_id", sa.CHAR(36), nullable=False),
        sa.Column("chart_of_account_id", sa.CHAR(36)),
        sa.Column("section", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["balance_sheet_id"],
            ["balance_sheets.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chart_of_account_id"],
            ["association_chart_of_accounts.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_balance_sheet_items_balance_sheet_id",
        "balance_sheet_items",
        ["balance_sheet_id"],
    )
    op.create_index(
        "ix_balance_sheet_items_section",
        "balance_sheet_items",
        ["section"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_balance_sheet_items_section",
        table_name="balance_sheet_items",
    )
    op.drop_index(
        "ix_balance_sheet_items_balance_sheet_id",
        table_name="balance_sheet_items",
    )
    op.drop_table("balance_sheet_items")
    op.drop_index(
        "ix_balance_sheets_as_on_date",
        table_name="balance_sheets",
    )
    op.drop_index(
        "ix_balance_sheets_association_id",
        table_name="balance_sheets",
    )
    op.drop_table("balance_sheets")
