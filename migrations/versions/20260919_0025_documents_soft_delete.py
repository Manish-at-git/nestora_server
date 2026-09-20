"""Add approved soft-delete flags to association and unit documents."""

from alembic import op
import sqlalchemy as sa

revision = "20260919_0025"
down_revision = "20260919_0024"
branch_labels = None
depends_on = None


def _add_if_missing(table: str) -> None:
    bind = op.get_bind()
    if "is_deleted" not in {column["name"] for column in sa.inspect(bind).get_columns(table)}:
        op.add_column(table, sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def upgrade() -> None:
    _add_if_missing("documents")
    _add_if_missing("unit_documents")


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("unit_documents", "documents"):
        if "is_deleted" in {column["name"] for column in sa.inspect(bind).get_columns(table)}:
            op.drop_column(table, "is_deleted")
