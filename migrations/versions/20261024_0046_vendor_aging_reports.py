"""Add normalized association Vendor Aging Report snapshots and invoice rows."""

import sqlalchemy as sa
from alembic import op

revision = "20261024_0046"
down_revision = "20261024_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendor_aging_reports",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("association_id", sa.CHAR(36), nullable=False),
        sa.Column("fiscal_period", sa.String(100), nullable=False),
        sa.Column("total_outstanding", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("overdue_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("current_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
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
            name="uq_vendor_aging_reports_association_period",
        ),
    )
    op.create_index(
        "ix_vendor_aging_reports_association_id",
        "vendor_aging_reports",
        ["association_id"],
    )
    op.create_table(
        "vendor_aging_rows",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("vendor_aging_report_id", sa.CHAR(36), nullable=False),
        sa.Column("vendor_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(150), nullable=False),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("current_due", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("days_1_30", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("days_31_60", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("days_61_90", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("days_over_90", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("current_due >= 0", name="ck_vendor_aging_rows_current_non_negative"),
        sa.CheckConstraint("days_1_30 >= 0", name="ck_vendor_aging_rows_1_30_non_negative"),
        sa.CheckConstraint("days_31_60 >= 0", name="ck_vendor_aging_rows_31_60_non_negative"),
        sa.CheckConstraint("days_61_90 >= 0", name="ck_vendor_aging_rows_61_90_non_negative"),
        sa.CheckConstraint("days_over_90 >= 0", name="ck_vendor_aging_rows_over_90_non_negative"),
        sa.UniqueConstraint(
            "vendor_aging_report_id",
            "vendor_name",
            "invoice_number",
            name="uq_vendor_aging_rows_report_vendor_invoice",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_aging_report_id"],
            ["vendor_aging_reports.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_vendor_aging_rows_report_id",
        "vendor_aging_rows",
        ["vendor_aging_report_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_vendor_aging_rows_report_id", table_name="vendor_aging_rows")
    op.drop_table("vendor_aging_rows")
    op.drop_index("ix_vendor_aging_reports_association_id", table_name="vendor_aging_reports")
    op.drop_table("vendor_aging_reports")
