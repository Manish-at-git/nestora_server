import uuid
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.associations.models import Association


class DelinquencyReport(Base):
    __tablename__ = "delinquency_reports"
    __table_args__ = (
        UniqueConstraint(
            "association_id",
            "fiscal_period",
            name="uq_delinquency_reports_association_period",
        ),
        CheckConstraint(
            "total_billed_amount >= 0",
            name="ck_delinquency_reports_billed_non_negative",
        ),
        CheckConstraint(
            "total_collected_amount >= 0",
            name="ck_delinquency_reports_collected_non_negative",
        ),
        CheckConstraint(
            "total_collected_amount <= total_billed_amount",
            name="ck_delinquency_reports_collection_within_billed",
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
    total_billed_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    total_collected_amount: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    total_outstanding: Mapped[float] = mapped_column(
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
    rows: Mapped[list["DelinquencyReportRow"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="DelinquencyReportRow.sort_order",
        lazy="selectin",
    )


class DelinquencyReportRow(Base):
    __tablename__ = "delinquency_report_rows"
    __table_args__ = (
        CheckConstraint(
            "outstanding_amount >= 0",
            name="ck_delinquency_rows_outstanding_non_negative",
        ),
        CheckConstraint(
            "days_overdue >= 0",
            name="ck_delinquency_rows_days_non_negative",
        ),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    delinquency_report_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("delinquency_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_number: Mapped[str] = mapped_column(String(100), nullable=False)
    block: Mapped[str | None] = mapped_column(String(100))
    charge_category: Mapped[str] = mapped_column(String(150), nullable=False)
    outstanding_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    days_overdue: Mapped[int] = mapped_column(Integer, nullable=False)
    last_payment_date: Mapped[date | None] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    report: Mapped[DelinquencyReport] = relationship(back_populates="rows")
