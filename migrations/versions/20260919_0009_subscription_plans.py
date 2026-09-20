"""Create subscription plans and soft-deletable plan-feature assignments."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0009"
down_revision = "20260919_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "subscription_plans" not in tables:
        op.create_table(
            "subscription_plans",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("code", sa.String(50), nullable=True),
            sa.Column("country", sa.String(10), nullable=False, server_default="IN"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("monthly_price", sa.Numeric(10, 2), nullable=True),
            sa.Column("yearly_price", sa.Numeric(10, 2), nullable=True),
            sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("code", name="uq_subscription_plans_code"),
        )
    else:
        columns = {column["name"] for column in inspector.get_columns("subscription_plans")}
        if "country" not in columns:
            op.add_column(
                "subscription_plans",
                sa.Column("country", sa.String(10), server_default="IN", nullable=False),
            )
        if "is_deleted" not in columns:
            op.add_column(
                "subscription_plans",
                sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
            )
        if "updated_at" not in columns:
            op.add_column("subscription_plans", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    if "subscription_plan_features" not in tables:
        op.create_table(
            "subscription_plan_features",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("plan_id", sa.CHAR(36), nullable=False),
            sa.Column("feature_id", sa.CHAR(36), nullable=False),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["feature_id"], ["features.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("plan_id", "feature_id", name="uq_subscription_plan_feature"),
        )
    elif "is_deleted" not in {column["name"] for column in inspector.get_columns("subscription_plan_features")}:
        op.add_column(
            "subscription_plan_features",
            sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        )

    indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("subscription_plan_features")
    }
    if "ix_subscription_plan_features_plan_id" not in indexes:
        op.create_index(
            "ix_subscription_plan_features_plan_id",
            "subscription_plan_features",
            ["plan_id"],
        )
    if "ix_subscription_plan_features_feature_id" not in indexes:
        op.create_index(
            "ix_subscription_plan_features_feature_id",
            "subscription_plan_features",
            ["feature_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "subscription_plan_features" in tables:
        indexes = {
            index["name"]
            for index in sa.inspect(bind).get_indexes("subscription_plan_features")
        }
        if "ix_subscription_plan_features_feature_id" in indexes:
            op.drop_index("ix_subscription_plan_features_feature_id", table_name="subscription_plan_features")
        if "ix_subscription_plan_features_plan_id" in indexes:
            op.drop_index("ix_subscription_plan_features_plan_id", table_name="subscription_plan_features")
    # Keep pre-existing legacy tables/data on downgrade; this migration is additive.
