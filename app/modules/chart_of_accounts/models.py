"""Persistence models for global and association-specific ledger accounts."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GlobalChartOfAccount(Base):
    __tablename__ = "global_chart_of_accounts"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    gl_code: Mapped[str] = mapped_column(String(255), nullable=False)
    gl_name: Mapped[str] = mapped_column(String(255), nullable=False)
    structure: Mapped[str | None] = mapped_column(String(255))
    grouping: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class AssociationChartOfAccount(Base):
    __tablename__ = "association_chart_of_accounts"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("associations.id", ondelete="CASCADE"), index=True)
    gl_code: Mapped[str] = mapped_column(String(255), nullable=False)
    gl_name: Mapped[str] = mapped_column(String(255), nullable=False)
    structure: Mapped[str | None] = mapped_column(String(255))
    grouping: Mapped[str | None] = mapped_column(String(255))
    mapped_from_global_id: Mapped[str | None] = mapped_column(CHAR(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
