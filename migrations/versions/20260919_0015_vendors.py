"""Add soft-delete support to vendors.

Revision ID: 20260919_0015
Revises: 20260919_0014
"""

from alembic import op
import sqlalchemy as sa

revision = "20260919_0015"
down_revision = "20260919_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "vendors" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("vendors")}
    if "is_deleted" not in columns:
        op.add_column(
            "vendors",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "is_deleted" in {column["name"] for column in sa.inspect(bind).get_columns("vendors")}:
        op.drop_column("vendors", "is_deleted")
