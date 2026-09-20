"""Persistence models for announcements and engagement rows."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, default="general")
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_by: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    association_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    audience: Mapped[str | None] = mapped_column(String(100), nullable=True, default="Homeowners")
    attachment_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class AnnouncementLike(Base):
    __tablename__ = "announcement_likes"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    announcement_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class AnnouncementComment(Base):
    __tablename__ = "announcement_comments"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    announcement_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

