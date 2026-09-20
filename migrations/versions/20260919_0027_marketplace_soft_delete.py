"""Add approved soft-delete flags to marketplace records."""

from alembic import op
import sqlalchemy as sa

revision = "20260919_0027"
down_revision = "20260919_0026"
branch_labels = None
depends_on = None


def _add_if_missing(table: str) -> None:
    bind = op.get_bind()
    if table not in sa.inspect(bind).get_table_names():
        return
    if "is_deleted" not in {column["name"] for column in sa.inspect(bind).get_columns(table)}:
        op.add_column(table, sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def upgrade() -> None:
    for table in (
        "marketplace_categories", "marketplace_items", "marketplace_images", "marketplace_favorites",
        "marketplace_chat", "marketplace_reports", "marketplace_views",
    ):
        _add_if_missing(table)


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "marketplace_views", "marketplace_reports", "marketplace_chat", "marketplace_favorites",
        "marketplace_images", "marketplace_items", "marketplace_categories",
    ):
        if table in sa.inspect(bind).get_table_names() and "is_deleted" in {column["name"] for column in sa.inspect(bind).get_columns(table)}:
            op.drop_column(table, "is_deleted")
