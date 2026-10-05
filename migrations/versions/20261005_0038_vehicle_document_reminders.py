"""Add renewal reminder dates for uploaded vehicle documents.

Revision ID: 20261005_0038
Revises: 20261003_0037
"""

import sqlalchemy as sa
from alembic import op


revision = "20261005_0038"
down_revision = "20261003_0037"
branch_labels = None
depends_on = None


def _column_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "vehicles" not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns("vehicles")}


def upgrade() -> None:
    column_names = _column_names()
    if not column_names:
        return

    if "insurance_reminder_date" not in column_names:
        op.add_column("vehicles", sa.Column("insurance_reminder_date", sa.Date(), nullable=True))
    if "puc_reminder_date" not in column_names:
        op.add_column("vehicles", sa.Column("puc_reminder_date", sa.Date(), nullable=True))


def downgrade() -> None:
    column_names = _column_names()
    if "puc_reminder_date" in column_names:
        op.drop_column("vehicles", "puc_reminder_date")
    if "insurance_reminder_date" in column_names:
        op.drop_column("vehicles", "insurance_reminder_date")
