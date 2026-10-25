import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.associations.models import Association
from app.modules.vendors.models import Vendor


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("association_id", "invoice_number", name="uq_invoices_association_number"),
        CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_non_negative"),
        CheckConstraint("discount_value >= 0", name="ck_invoices_discount_non_negative"),
        CheckConstraint("tax_rate >= 0", name="ck_invoices_tax_rate_non_negative"),
        CheckConstraint("tax_amount >= 0", name="ck_invoices_tax_amount_non_negative"),
        CheckConstraint("grand_total >= 0", name="ck_invoices_total_non_negative"),
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("associations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # These legacy columns remain populated for records created before 0049.
    legacy_vendor_name: Mapped[str] = mapped_column("vendor_name", String(255), nullable=False)
    legacy_category: Mapped[str] = mapped_column("category", String(150), nullable=False)
    legacy_description: Mapped[str | None] = mapped_column("description", String(1000))
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    tax_percentage: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=Decimal("0.00")
    )
    vendor_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    billing_address: Mapped[str | None] = mapped_column(Text)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_terms: Mapped[str | None] = mapped_column(String(255))
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    discount_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    tax_type: Mapped[str | None] = mapped_column(String(100))
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=Decimal("0.00")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    payment_date: Mapped[date | None] = mapped_column(Date)
    payment_method: Mapped[str | None] = mapped_column(String(100))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL")
    )
    updated_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL")
    )
    deleted_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    association: Mapped[Association] = relationship(Association, lazy="joined")
    vendor: Mapped[Vendor | None] = relationship(Vendor, lazy="joined")
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.sort_order",
        lazy="selectin",
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        UniqueConstraint("invoice_id", "sort_order", name="uq_invoice_lines_order"),
        CheckConstraint("quantity > 0", name="ck_invoice_lines_quantity_positive"),
        CheckConstraint("rate >= 0", name="ck_invoice_lines_rate_non_negative"),
        CheckConstraint("amount >= 0", name="ck_invoice_lines_amount_non_negative"),
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL")
    )
    updated_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    invoice: Mapped[Invoice] = relationship(back_populates="lines")
