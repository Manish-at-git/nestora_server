"""Add the soft-delete marker used by entity management."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0005"
down_revision = "20260919_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep entity rows while hiding them from normal application queries."""
    op.add_column(
        "entities",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    """Remove the entity soft-delete marker when rolling back this migration."""
    op.drop_column("entities", "is_deleted")
