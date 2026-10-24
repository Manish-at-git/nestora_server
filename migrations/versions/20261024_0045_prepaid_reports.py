"""Add normalized association Prepaid Report snapshots and member rows."""

import sqlalchemy as sa
from alembic import op

revision = "20261024_0045"
down_revision = "20261024_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prepaid_reports",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("association_id", sa.CHAR(36), nullable=False),
        sa.Column("fiscal_period", sa.String(100), nullable=False),
        sa.Column("total_prepaid_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_used_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_available_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_by", sa.CHAR(36)),
        sa.Column("updated_by", sa.CHAR(36)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["association_id"], ["associations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["accounts.account_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["accounts.account_id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "association_id",
            "fiscal_period",
            name="uq_prepaid_reports_association_period",
        ),
    )
    op.create_index(
        "ix_prepaid_reports_association_id",
        "prepaid_reports",
        ["association_id"],
    )
    op.create_table(
        "prepaid_report_rows",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("prepaid_report_id", sa.CHAR(36), nullable=False),
        sa.Column("member_name", sa.String(255), nullable=False),
        sa.Column("unit_number", sa.String(100), nullable=False),
        sa.Column("block", sa.String(100)),
        sa.Column("category", sa.String(150), nullable=False),
        sa.Column("prepaid_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("used_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "prepaid_amount >= 0",
            name="ck_prepaid_report_rows_prepaid_non_negative",
        ),
        sa.CheckConstraint(
            "used_amount >= 0",
            name="ck_prepaid_report_rows_used_non_negative",
        ),
        sa.CheckConstraint(
            "used_amount <= prepaid_amount",
            name="ck_prepaid_report_rows_used_within_prepaid",
        ),
        sa.ForeignKeyConstraint(
            ["prepaid_report_id"],
            ["prepaid_reports.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_prepaid_report_rows_report_id",
        "prepaid_report_rows",
        ["prepaid_report_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_prepaid_report_rows_report_id", table_name="prepaid_report_rows")
    op.drop_table("prepaid_report_rows")
    op.drop_index("ix_prepaid_reports_association_id", table_name="prepaid_reports")
    op.drop_table("prepaid_reports")
