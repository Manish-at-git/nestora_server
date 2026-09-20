"""Add Association fields required by the modular directory and soft delete."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0010"
down_revision = "20260919_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "associations" not in tables:
        op.create_table(
            "associations",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("association_code", sa.String(10), nullable=True),
            sa.Column("entity_id", sa.CHAR(36), nullable=True),
            sa.Column("address_line_1", sa.String(255), nullable=True),
            sa.Column("address_line_2", sa.String(255), nullable=True),
            sa.Column("city", sa.String(100), nullable=True),
            sa.Column("state", sa.String(100), nullable=True),
            sa.Column("pincode", sa.String(20), nullable=True),
            sa.Column("url", sa.String(255), nullable=True),
            sa.Column("contract_url", sa.String(255), nullable=True),
            sa.Column("current_plan_id", sa.CHAR(36), nullable=True),
            sa.Column("subscription_status", sa.String(50), nullable=True),
            sa.Column("subscription_start", sa.Date(), nullable=True),
            sa.Column("subscription_end", sa.Date(), nullable=True),
            sa.Column("payment_status", sa.String(50), nullable=True),
            sa.Column("renewal_date", sa.Date(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("country", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        return

    columns = {column["name"] for column in inspector.get_columns("associations")}
    additions = {
        "association_code": sa.Column("association_code", sa.String(10), nullable=True),
        "entity_id": sa.Column("entity_id", sa.CHAR(36), nullable=True),
        "address_line_1": sa.Column("address_line_1", sa.String(255), nullable=True),
        "address_line_2": sa.Column("address_line_2", sa.String(255), nullable=True),
        "city": sa.Column("city", sa.String(100), nullable=True),
        "state": sa.Column("state", sa.String(100), nullable=True),
        "pincode": sa.Column("pincode", sa.String(20), nullable=True),
        "url": sa.Column("url", sa.String(255), nullable=True),
        "contract_url": sa.Column("contract_url", sa.String(255), nullable=True),
        "current_plan_id": sa.Column("current_plan_id", sa.CHAR(36), nullable=True),
        "subscription_status": sa.Column("subscription_status", sa.String(50), nullable=True),
        "subscription_start": sa.Column("subscription_start", sa.Date(), nullable=True),
        "subscription_end": sa.Column("subscription_end", sa.Date(), nullable=True),
        "payment_status": sa.Column("payment_status", sa.String(50), nullable=True),
        "renewal_date": sa.Column("renewal_date", sa.Date(), nullable=True),
        "is_deleted": sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        "updated_at": sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("associations", column)


def downgrade() -> None:
    # Keep legacy association data intact on downgrade; this migration is additive.
    pass
