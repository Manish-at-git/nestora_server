"""Add user soft deletion and the account-to-user link."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0014"
down_revision = "20260919_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "user_details" in tables:
        columns = {column["name"] for column in inspector.get_columns("user_details")}
        if "is_deleted" not in columns:
            op.add_column(
                "user_details",
                sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            )

    if "accounts" in tables:
        columns = {column["name"] for column in inspector.get_columns("accounts")}
        if "user_id" not in columns:
            op.add_column("accounts", sa.Column("user_id", sa.CHAR(36), nullable=True))
        foreign_keys = {
            (tuple(key["constrained_columns"]), key["referred_table"])
            for key in sa.inspect(bind).get_foreign_keys("accounts")
        }
        if (("user_id",), "user_details") not in foreign_keys:
            op.create_foreign_key(
                "fk_accounts_user",
                "accounts",
                "user_details",
                ["user_id"],
                ["user_id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    # Preserve user records and account links on downgrade.
    pass
