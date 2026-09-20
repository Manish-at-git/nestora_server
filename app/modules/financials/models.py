"""Persistence model for published association financial reports."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FinancialReport(Base):
    __tablename__ = "financial_reports"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("associations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    published_month: Mapped[str] = mapped_column(String(50), nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    association = relationship("Association", foreign_keys=[association_id], lazy="joined")
