"""Align the historical Balance Sheet tables with Excel import.

Revision ID: 20261018_0041
Revises: 20261011_0040
"""

import sqlalchemy as sa
from alembic import op

revision = "20261018_0041"
down_revision = "20261011_0040"
branch_labels = None
depends_on = None


SECTION_CHECK = (
    "section IN ('current_asset', 'non_current_asset', "
    "'current_liability', 'non_current_liability', 'equity')"
)


def upgrade() -> None:
    op.alter_column(
        "balance_sheet_items",
        "name",
        new_column_name="account_name",
        existing_type=sa.String(255),
        existing_nullable=False,
    )
    op.alter_column(
        "balance_sheet_items",
        "amount",
        existing_type=sa.Numeric(15, 2),
        type_=sa.Numeric(18, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "balance_sheet_items",
        "section",
        existing_type=sa.String(50),
        type_=sa.String(30),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_balance_sheet_items_section",
        "balance_sheet_items",
        SECTION_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_balance_sheet_items_section",
        "balance_sheet_items",
        type_="check",
    )
    op.alter_column(
        "balance_sheet_items",
        "section",
        existing_type=sa.String(30),
        type_=sa.String(50),
        existing_nullable=False,
    )
    op.alter_column(
        "balance_sheet_items",
        "amount",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Numeric(15, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "balance_sheet_items",
        "account_name",
        new_column_name="name",
        existing_type=sa.String(255),
        existing_nullable=False,
    )
