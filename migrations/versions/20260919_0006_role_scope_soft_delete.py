"""Add entity scope and soft-delete state to IAM roles."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0006"
down_revision = "20260919_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserve role rows while supporting optional entity scope and soft deletion."""
    op.add_column("roles", sa.Column("entity_id", sa.CHAR(length=36), nullable=True))
    op.add_column(
        "roles",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_foreign_key(
        "fk_roles_entity",
        "roles",
        "entities",
        ["entity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_roles_entity_id", "roles", ["entity_id"], unique=False)


def downgrade() -> None:
    """Remove role scope and soft-delete columns when rolling back this migration."""
    op.drop_index("ix_roles_entity_id", table_name="roles")
    op.drop_constraint("fk_roles_entity", "roles", type_="foreignkey")
    op.drop_column("roles", "is_deleted")
    op.drop_column("roles", "entity_id")
