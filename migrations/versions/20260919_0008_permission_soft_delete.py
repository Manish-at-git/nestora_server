"""Add soft-delete state to role-feature permission assignments."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0008"
down_revision = "20260919_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "role_feature_permissions",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("role_feature_permissions", "is_deleted")
