"""Create the association bank account table and add soft deletion."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0011"
down_revision = "20260919_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "association_bank_accounts" not in tables:
        op.create_table(
            "association_bank_accounts",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("association_id", sa.CHAR(36), nullable=False),
            sa.Column("account_name", sa.String(255), nullable=False),
            sa.Column("account_holder_name", sa.String(255), nullable=False),
            sa.Column("bank_name", sa.String(255), nullable=False),
            sa.Column("account_number", sa.Text(), nullable=False),
            sa.Column("ifsc_code", sa.String(50), nullable=False),
            sa.Column("branch_name", sa.String(255), nullable=True),
            sa.Column("account_type", sa.String(50), nullable=False, server_default="Current"),
            sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
            sa.Column("upi_id", sa.String(255), nullable=True),
            sa.Column("qr_code_url", sa.String(255), nullable=True),
            sa.Column("gateway_provider", sa.String(100), nullable=True),
            sa.Column("merchant_id", sa.String(255), nullable=True),
            sa.Column("api_key", sa.Text(), nullable=True),
            sa.Column("api_secret", sa.Text(), nullable=True),
            sa.Column("webhook_secret", sa.Text(), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(20), nullable=False, server_default="Active"),
            sa.Column("created_by", sa.CHAR(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_by", sa.CHAR(36), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.ForeignKeyConstraint(["association_id"], ["associations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["accounts.account_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by"], ["accounts.account_id"], ondelete="SET NULL"),
        )
    else:
        columns = {column["name"] for column in inspector.get_columns("association_bank_accounts")}
        if "is_deleted" not in columns:
            op.add_column(
                "association_bank_accounts",
                sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            )

    indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("association_bank_accounts")
    }
    if "ix_association_bank_accounts_association_id" not in indexes:
        op.create_index(
            "ix_association_bank_accounts_association_id",
            "association_bank_accounts",
            ["association_id"],
        )


def downgrade() -> None:
    # Preserve legacy bank rows on downgrade; this migration is additive.
    pass
