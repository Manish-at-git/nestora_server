"""Add normalized association Income Statement snapshots and line items."""

import sqlalchemy as sa
from alembic import op

revision = "20261018_0042"
down_revision = "20261018_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "income_statements",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("association_id", sa.CHAR(36), nullable=False),
        sa.Column("fiscal_period", sa.String(100), nullable=False),
        sa.Column("total_income", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_expenses", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("net_surplus", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("operating_margin_pct", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("income_growth_pct", sa.Numeric(8, 2)),
        sa.Column("expenses_growth_pct", sa.Numeric(8, 2)),
        sa.Column("net_surplus_growth_pct", sa.Numeric(8, 2)),
        sa.Column("operating_margin_growth_pct", sa.Numeric(8, 2)),
        sa.Column("insights_json", sa.Text()),
        sa.Column("monthly_trend_json", sa.Text()),
        sa.Column("created_by", sa.CHAR(36)),
        sa.Column("updated_by", sa.CHAR(36)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["association_id"], ["associations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["accounts.account_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["accounts.account_id"], ondelete="SET NULL"),
        sa.UniqueConstraint("association_id", "fiscal_period", name="uq_income_statements_association_period"),
    )
    op.create_index("ix_income_statements_association_id", "income_statements", ["association_id"])
    op.create_table(
        "income_statement_items",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("income_statement_id", sa.CHAR(36), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("current_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("previous_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["income_statement_id"], ["income_statements.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_income_statement_items_statement_id", "income_statement_items", ["income_statement_id"])
    op.create_index("ix_income_statement_items_item_type", "income_statement_items", ["item_type"])


def downgrade() -> None:
    op.drop_index("ix_income_statement_items_item_type", table_name="income_statement_items")
    op.drop_index("ix_income_statement_items_statement_id", table_name="income_statement_items")
    op.drop_table("income_statement_items")
    op.drop_index("ix_income_statements_association_id", table_name="income_statements")
    op.drop_table("income_statements")
