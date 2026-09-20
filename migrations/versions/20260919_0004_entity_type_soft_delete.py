"""Add the soft-delete marker used by entity type management."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0004"
down_revision = "20260919_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep entity type rows while hiding them from normal application queries."""
    op.add_column(
        "entity_types",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    """Remove the soft-delete marker when rolling back this migration."""
    op.drop_column("entity_types", "is_deleted")
