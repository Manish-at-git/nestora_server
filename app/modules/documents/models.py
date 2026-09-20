"""Persistence models for association documents and unit documents."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CHAR, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("associations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(100))
    document_type: Mapped[str | None] = mapped_column(String(50))
    category: Mapped[str | None] = mapped_column(String(50))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_url: Mapped[str | None] = mapped_column(String(500))
    file_type: Mapped[str | None] = mapped_column(String(20))
    file_size_kb: Mapped[int | None] = mapped_column(Integer)
    department: Mapped[str | None] = mapped_column(String(100))
    related_module: Mapped[str | None] = mapped_column(String(50))
    visibility: Mapped[str | None] = mapped_column(String(255))
    allow_download: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    reminder_before_expiry_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(20), default="Active", server_default="Active")
    keywords: Mapped[str | None] = mapped_column(String(255))
    remarks: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)


class UnitDocument(Base):
    __tablename__ = "unit_documents"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("associations.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("units.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    file_url: Mapped[str | None] = mapped_column(String(255))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_type: Mapped[str | None] = mapped_column(String(50))
    file_size_kb: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
