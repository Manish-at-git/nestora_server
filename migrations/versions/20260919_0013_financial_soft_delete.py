"""Add soft deletion to published financial reports."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0013"
down_revision = "20260919_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "financial_reports" not in tables:
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("financial_reports")}
    if "is_deleted" not in columns:
        op.add_column(
            "financial_reports",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    # Preserve report records on downgrade; this migration is additive.
    pass
