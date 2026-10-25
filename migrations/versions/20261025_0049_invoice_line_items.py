"""Extend the original invoice table with vendor references and line items.

Revision ID: 20261025_0049
Revises: 20261025_0048
"""

import sqlalchemy as sa
from alembic import op

revision = "20261025_0049"
down_revision = "20261025_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("vendor_id", sa.CHAR(36), nullable=True))
    op.add_column("invoices", sa.Column("billing_address", sa.Text(), nullable=True))
    op.add_column("invoices", sa.Column("issue_date", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("payment_terms", sa.String(255), nullable=True))
    op.add_column(
        "invoices", sa.Column("discount_type", sa.String(20), nullable=False, server_default="none")
    )
    op.add_column(
        "invoices",
        sa.Column("discount_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.add_column("invoices", sa.Column("tax_type", sa.String(100), nullable=True))
    op.add_column(
        "invoices", sa.Column("tax_rate", sa.Numeric(7, 2), nullable=False, server_default="0")
    )
    op.add_column("invoices", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "invoices", sa.Column("grand_total", sa.Numeric(18, 2), nullable=False, server_default="0")
    )
    op.add_column("invoices", sa.Column("deleted_by", sa.CHAR(36), nullable=True))
    op.add_column("invoices", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "invoices", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0")
    )
    op.create_foreign_key(
        "fk_invoices_vendor_id", "invoices", "vendors", ["vendor_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_invoices_deleted_by",
        "invoices",
        "accounts",
        ["deleted_by"],
        ["account_id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_invoices_vendor_id", "invoices", ["vendor_id"])
    op.execute(
        "UPDATE invoices SET issue_date = invoice_date, "
        "tax_rate = tax_percentage, grand_total = subtotal + tax_amount"
    )
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column(
            "invoice_id",
            sa.CHAR(36),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("rate", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_by", sa.CHAR(36), sa.ForeignKey("accounts.account_id", ondelete="SET NULL")
        ),
        sa.Column(
            "updated_by", sa.CHAR(36), sa.ForeignKey("accounts.account_id", ondelete="SET NULL")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("invoice_id", "sort_order", name="uq_invoice_lines_order"),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_lines_quantity_positive"),
        sa.CheckConstraint("rate >= 0", name="ck_invoice_lines_rate_non_negative"),
        sa.CheckConstraint("amount >= 0", name="ck_invoice_lines_amount_non_negative"),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_vendor_id", table_name="invoices")
    op.drop_constraint("fk_invoices_deleted_by", "invoices", type_="foreignkey")
    op.drop_constraint("fk_invoices_vendor_id", "invoices", type_="foreignkey")
    for column in (
        "is_deleted",
        "deleted_at",
        "deleted_by",
        "grand_total",
        "discount_amount",
        "notes",
        "tax_rate",
        "tax_type",
        "discount_value",
        "discount_type",
        "payment_terms",
        "issue_date",
        "billing_address",
        "vendor_id",
    ):
        op.drop_column("invoices", column)
