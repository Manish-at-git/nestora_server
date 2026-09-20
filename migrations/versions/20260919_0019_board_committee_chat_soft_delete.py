"""Add soft-delete flag to the shared board/committee chat table."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0019"
down_revision = "20260919_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("board_committee_chat")}
    if "is_deleted" not in columns:
        op.add_column(
            "board_committee_chat",
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("board_committee_chat")}
    if "is_deleted" in columns:
        op.drop_column("board_committee_chat", "is_deleted")

