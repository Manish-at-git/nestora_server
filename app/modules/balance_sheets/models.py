"""Normalized association Balance Sheet snapshots and line items."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
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


class BalanceSheet(Base):
    __tablename__ = "balance_sheets"
    __table_args__ = (
        UniqueConstraint(
            "association_id",
            "as_on_date",
            name="uq_balance_sheets_association_date",
        ),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    association_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("associations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    as_on_date: Mapped[date] = mapped_column(Date, nullable=False)
    health_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    health_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("accounts.account_id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("accounts.account_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )

    association: Mapped[Association] = relationship(
        Association,
        foreign_keys=[association_id],
        lazy="joined",
    )
    items: Mapped[list["BalanceSheetItem"]] = relationship(
        back_populates="balance_sheet",
        cascade="all, delete-orphan",
        order_by="BalanceSheetItem.sort_order",
        lazy="selectin",
    )


class BalanceSheetItem(Base):
    __tablename__ = "balance_sheet_items"

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    balance_sheet_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("balance_sheets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chart_of_account_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("association_chart_of_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    section: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    balance_sheet: Mapped[BalanceSheet] = relationship(back_populates="items")
