"""Create generic RBAC tables used by Nestora's IAM module.

This migration creates only the two reusable tables needed to represent every
legacy feature and every role-feature CRUD assignment. It does not copy data.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260919_0002"
down_revision = "20260917_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create feature and per-role permission tables with legacy-compatible fields."""
    op.create_table(
        "features",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.CHAR(length=36), nullable=True),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("route", sa.String(length=255), nullable=True),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["features.id"], name="fk_features_parent", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_features"),
        sa.UniqueConstraint("code", name="uq_features_code"),
    )
    op.create_index("ix_features_parent_id", "features", ["parent_id"], unique=False)

    op.create_table(
        "role_feature_permissions",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("role_id", sa.CHAR(length=36), nullable=False),
        sa.Column("feature_id", sa.CHAR(length=36), nullable=False),
        sa.Column("can_create", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("can_view", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("can_update", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("can_delete", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("sidebar_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_rfp_role", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feature_id"], ["features.id"], name="fk_rfp_feature", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_role_feature_permissions"),
        sa.UniqueConstraint("role_id", "feature_id", name="uq_role_feature_permissions_role_feature"),
    )
    op.create_index("ix_rfp_role_id", "role_feature_permissions", ["role_id"], unique=False)
    op.create_index("ix_rfp_feature_id", "role_feature_permissions", ["feature_id"], unique=False)


def downgrade() -> None:
    """Drop only the generic RBAC tables introduced by this revision."""
    op.drop_index("ix_rfp_feature_id", table_name="role_feature_permissions")
    op.drop_index("ix_rfp_role_id", table_name="role_feature_permissions")
    op.drop_table("role_feature_permissions")
    op.drop_index("ix_features_parent_id", table_name="features")
    op.drop_table("features")
