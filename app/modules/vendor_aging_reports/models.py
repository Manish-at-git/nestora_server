import uuid
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.associations.models import Association


class VendorAgingReport(Base):
    __tablename__ = "vendor_aging_reports"
    __table_args__ = (
        UniqueConstraint(
            "association_id",
            "fiscal_period",
            name="uq_vendor_aging_reports_association_period",
        ),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    association_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("associations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fiscal_period: Mapped[str] = mapped_column(String(100), nullable=False)
    total_outstanding: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False, default=0
    )
    overdue_amount: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False, default=0
    )
    current_amount: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False, default=0
    )
    created_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL")
    )
    updated_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    association: Mapped[Association] = relationship(Association, lazy="joined")
    rows: Mapped[list["VendorAgingRow"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="VendorAgingRow.sort_order",
        lazy="selectin",
    )


class VendorAgingRow(Base):
    __tablename__ = "vendor_aging_rows"
    __table_args__ = (
        UniqueConstraint(
            "vendor_aging_report_id",
            "vendor_name",
            "invoice_number",
            name="uq_vendor_aging_rows_report_vendor_invoice",
        ),
        CheckConstraint("current_due >= 0", name="ck_vendor_aging_rows_current_non_negative"),
        CheckConstraint("days_1_30 >= 0", name="ck_vendor_aging_rows_1_30_non_negative"),
        CheckConstraint("days_31_60 >= 0", name="ck_vendor_aging_rows_31_60_non_negative"),
        CheckConstraint("days_61_90 >= 0", name="ck_vendor_aging_rows_61_90_non_negative"),
        CheckConstraint("days_over_90 >= 0", name="ck_vendor_aging_rows_over_90_non_negative"),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    vendor_aging_report_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("vendor_aging_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(150), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_due: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    days_1_30: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    days_31_60: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    days_61_90: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    days_over_90: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    report: Mapped[VendorAgingReport] = relationship(back_populates="rows")
