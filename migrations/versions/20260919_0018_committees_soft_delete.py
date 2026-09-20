"""Add soft-delete flags to committee definitions and memberships."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0018"
down_revision = "20260919_0017"
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
    _add_if_missing("committees")
    _add_if_missing("committee_members")
    _add_if_missing("board_committee_chat")


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("board_committee_chat", "committee_members", "committees"):
        columns = {column["name"] for column in sa.inspect(bind).get_columns(table)}
        if "is_deleted" in columns:
            op.drop_column(table, "is_deleted")
