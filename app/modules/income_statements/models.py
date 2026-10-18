import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.associations.models import Association


class IncomeStatement(Base):
    __tablename__ = "income_statements"
    __table_args__ = (UniqueConstraint("association_id", "fiscal_period", name="uq_income_statements_association_period"),)

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("associations.id", ondelete="CASCADE"), nullable=False, index=True)
    fiscal_period: Mapped[str] = mapped_column(String(100), nullable=False)
    total_income: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    total_expenses: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    net_surplus: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    operating_margin_pct: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    income_growth_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    expenses_growth_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    net_surplus_growth_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    operating_margin_growth_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    insights_json: Mapped[str | None] = mapped_column(Text)
    monthly_trend_json: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL"))
    updated_by: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    association: Mapped[Association] = relationship(Association, lazy="joined")
    items: Mapped[list["IncomeStatementItem"]] = relationship(back_populates="statement", cascade="all, delete-orphan", order_by="IncomeStatementItem.sort_order", lazy="selectin")


class IncomeStatementItem(Base):
    __tablename__ = "income_statement_items"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    income_statement_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("income_statements.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    current_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    previous_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(default=0)

    statement: Mapped[IncomeStatement] = relationship(back_populates="items")
