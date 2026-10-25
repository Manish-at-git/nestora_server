"""Store the association payment account selected for each invoice.

Revision ID: 20261025_0050
Revises: 20261025_0049
"""

import sqlalchemy as sa
from alembic import op

revision = "20261025_0050"
down_revision = "20261025_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("bank_account_id", sa.CHAR(36), nullable=True))
    op.create_foreign_key(
        "fk_invoices_bank_account_id",
        "invoices",
        "association_bank_accounts",
        ["bank_account_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_invoices_bank_account_id", "invoices", ["bank_account_id"])


def downgrade() -> None:
    op.drop_index("ix_invoices_bank_account_id", table_name="invoices")
    op.drop_constraint("fk_invoices_bank_account_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "bank_account_id")
