"""Add normalized association-scoped invoices.

Revision ID: 20261025_0048
Revises: 20261024_0047
"""

from alembic import op
import sqlalchemy as sa

revision = "20261025_0048"
down_revision = "20261024_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("association_id", sa.CHAR(36), sa.ForeignKey("associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("vendor_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(150), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_percentage", sa.Numeric(7, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payment_date", sa.Date()),
        sa.Column("payment_method", sa.String(100)),
        sa.Column("created_by", sa.CHAR(36), sa.ForeignKey("accounts.account_id", ondelete="SET NULL")),
        sa.Column("updated_by", sa.CHAR(36), sa.ForeignKey("accounts.account_id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("association_id", "invoice_number", name="uq_invoices_association_number"),
        sa.CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_non_negative"),
        sa.CheckConstraint("tax_percentage >= 0", name="ck_invoices_tax_percentage_non_negative"),
        sa.CheckConstraint("tax_amount >= 0", name="ck_invoices_tax_amount_non_negative"),
    )
    op.create_index("ix_invoices_association_id", "invoices", ["association_id"])


def downgrade() -> None:
    op.drop_index("ix_invoices_association_id", table_name="invoices")
    op.drop_table("invoices")
