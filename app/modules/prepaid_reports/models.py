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


class PrepaidReport(Base):
    __tablename__ = "prepaid_reports"
    __table_args__ = (
        UniqueConstraint(
            "association_id",
            "fiscal_period",
            name="uq_prepaid_reports_association_period",
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
    total_prepaid_amount: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False, default=0
    )
    total_used_amount: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False, default=0
    )
    total_available_balance: Mapped[float] = mapped_column(
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
    rows: Mapped[list["PrepaidReportRow"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="PrepaidReportRow.sort_order",
        lazy="selectin",
    )


class PrepaidReportRow(Base):
    __tablename__ = "prepaid_report_rows"
    __table_args__ = (
        CheckConstraint(
            "prepaid_amount >= 0",
            name="ck_prepaid_report_rows_prepaid_non_negative",
        ),
        CheckConstraint(
            "used_amount >= 0",
            name="ck_prepaid_report_rows_used_non_negative",
        ),
        CheckConstraint(
            "used_amount <= prepaid_amount",
            name="ck_prepaid_report_rows_used_within_prepaid",
        ),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    prepaid_report_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("prepaid_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_number: Mapped[str] = mapped_column(String(100), nullable=False)
    block: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(150), nullable=False)
    prepaid_amount: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False, default=0
    )
    used_amount: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False, default=0
    )
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)

    report: Mapped[PrepaidReport] = relationship(back_populates="rows")
