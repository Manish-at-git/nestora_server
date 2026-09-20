"""Add soft-delete state to IAM features."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0007"
down_revision = "20260919_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "features",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("features", "is_deleted")
