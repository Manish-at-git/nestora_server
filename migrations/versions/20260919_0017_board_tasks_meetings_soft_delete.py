"""Add soft-delete flags to the board-task and meeting domains."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0017"
down_revision = "20260919_0016"
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
    for table in (
        "board_tasks",
        "board_task_messages",
        "meetings",
        "meeting_attendance",
    ):
        _add_if_missing(table)


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("meeting_attendance", "meetings", "board_task_messages", "board_tasks"):
        columns = {column["name"] for column in sa.inspect(bind).get_columns(table)}
        if "is_deleted" in columns:
            op.drop_column(table, "is_deleted")
