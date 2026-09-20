"""Add approved soft-delete flags to event records and engagement rows."""

from alembic import op
import sqlalchemy as sa

revision = "20260919_0022"
down_revision = "20260919_0021"
branch_labels = None
depends_on = None


def _add_if_missing(table: str) -> None:
    bind = op.get_bind()
    if "is_deleted" not in {column["name"] for column in sa.inspect(bind).get_columns(table)}:
        op.add_column(table, sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def upgrade() -> None:
    for table in ("events", "event_rsvps", "event_likes", "event_comments"):
        _add_if_missing(table)


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("event_comments", "event_likes", "event_rsvps", "events"):
        if "is_deleted" in {column["name"] for column in sa.inspect(bind).get_columns(table)}:
            op.drop_column(table, "is_deleted")
