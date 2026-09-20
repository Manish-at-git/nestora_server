"""Add soft-delete flags to announcements and engagement rows."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0021"
down_revision = "20260919_0020"
branch_labels = None
depends_on = None


def _add_if_missing(table: str) -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns(table)}
    if "is_deleted" not in columns:
        op.add_column(
            table,
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def upgrade() -> None:
    for table in ("announcements", "announcement_likes", "announcement_comments"):
        _add_if_missing(table)


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("announcement_comments", "announcement_likes", "announcements"):
        columns = {column["name"] for column in sa.inspect(bind).get_columns(table)}
        if "is_deleted" in columns:
            op.drop_column(table, "is_deleted")

