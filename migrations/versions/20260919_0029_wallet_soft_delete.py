"""Add approved soft-delete flags to wallet records."""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0029"
down_revision = "20260919_0028"
branch_labels = None
depends_on = None

TABLES = ("wallets", "wallet_transactions", "wallet_topups", "wallet_ledger", "password_reset_challenges")


def _create_if_missing() -> None:
    """Create the two core wallet tables when a deployment did not inherit legacy DDL."""
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "wallets" not in tables:
        op.create_table(
            "wallets",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("account_id", sa.CHAR(36), nullable=False, unique=True),
            sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("reward_points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("security_pin", sa.String(255)),
            sa.Column("status", sa.String(50), server_default="active"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"], ondelete="CASCADE"),
        )
        tables.add("wallets")
    if "wallet_transactions" not in tables:
        op.create_table(
            "wallet_transactions",
            sa.Column("id", sa.CHAR(36), primary_key=True),
            sa.Column("wallet_id", sa.CHAR(36), nullable=False),
            sa.Column("type", sa.String(50), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("status", sa.String(50), server_default="Completed"),
            sa.Column("reference_number", sa.String(100)),
            sa.Column("description", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
        )


def _add_if_missing(table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(table)}
    if "is_deleted" not in columns:
        op.add_column(table, sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def upgrade() -> None:
    _create_if_missing()
    for table in TABLES:
        _add_if_missing(table)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in reversed(TABLES):
        if table in inspector.get_table_names() and "is_deleted" in {column["name"] for column in inspector.get_columns(table)}:
            op.drop_column(table, "is_deleted")
