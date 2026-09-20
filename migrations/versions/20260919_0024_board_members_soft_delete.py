"""Add approved soft-delete support to board memberships."""

from alembic import op
import sqlalchemy as sa

revision = "20260919_0024"
down_revision = "20260919_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("board_members")}
    if "is_deleted" not in columns:
        op.add_column("board_members", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("board_members")}
    if "is_deleted" in columns:
        op.drop_column("board_members", "is_deleted")
