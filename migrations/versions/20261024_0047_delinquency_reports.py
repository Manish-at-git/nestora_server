"""Add normalized association Delinquency Report snapshots and member rows."""

import sqlalchemy as sa
from alembic import op

revision = "20261024_0047"
down_revision = "20261024_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delinquency_reports",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("association_id", sa.CHAR(36), nullable=False),
        sa.Column("fiscal_period", sa.String(100), nullable=False),
        sa.Column("total_billed_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_collected_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "total_outstanding",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_by", sa.CHAR(36)),
        sa.Column("updated_by", sa.CHAR(36)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime()),
        sa.CheckConstraint(
            "total_billed_amount >= 0",
            name="ck_delinquency_reports_billed_non_negative",
        ),
        sa.CheckConstraint(
            "total_collected_amount >= 0",
            name="ck_delinquency_reports_collected_non_negative",
        ),
        sa.CheckConstraint(
            "total_collected_amount <= total_billed_amount",
            name="ck_delinquency_reports_collection_within_billed",
        ),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["associations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["accounts.account_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["accounts.account_id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "association_id",
            "fiscal_period",
            name="uq_delinquency_reports_association_period",
        ),
    )
    op.create_index(
        "ix_delinquency_reports_association_id",
        "delinquency_reports",
        ["association_id"],
    )
    op.create_table(
        "delinquency_report_rows",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("delinquency_report_id", sa.CHAR(36), nullable=False),
        sa.Column("member_name", sa.String(255), nullable=False),
        sa.Column("unit_number", sa.String(100), nullable=False),
        sa.Column("block", sa.String(100)),
        sa.Column("charge_category", sa.String(150), nullable=False),
        sa.Column("outstanding_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("days_overdue", sa.Integer(), nullable=False),
        sa.Column("last_payment_date", sa.Date()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "outstanding_amount >= 0",
            name="ck_delinquency_rows_outstanding_non_negative",
        ),
        sa.CheckConstraint(
            "days_overdue >= 0",
            name="ck_delinquency_rows_days_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["delinquency_report_id"],
            ["delinquency_reports.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_delinquency_report_rows_report_id",
        "delinquency_report_rows",
        ["delinquency_report_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_delinquency_report_rows_report_id",
        table_name="delinquency_report_rows",
    )
    op.drop_table("delinquency_report_rows")
    op.drop_index(
        "ix_delinquency_reports_association_id",
        table_name="delinquency_reports",
    )
    op.drop_table("delinquency_reports")
