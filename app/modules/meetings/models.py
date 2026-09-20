"""Persistence models for meetings and attendance."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import CHAR, Boolean, Date, DateTime, ForeignKey, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.meetings.constants import MeetingStatus


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    meeting_type: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False)
    audience: Mapped[str] = mapped_column(String(100), nullable=False)
    agenda: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    meeting_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration: Mapped[str] = mapped_column(String(50), nullable=False)
    venue: Mapped[str] = mapped_column(String(100), nullable=False)
    meeting_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organizer: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    attachment_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=MeetingStatus.SCHEDULED)
    meeting_minutes: Mapped[str | None] = mapped_column(Text, nullable=True)
    discussed_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_block_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MeetingAttendance(Base):
    __tablename__ = "meeting_attendance"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
