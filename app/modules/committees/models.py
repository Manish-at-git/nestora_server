"""Persistence models for committees and their memberships."""

import uuid
from datetime import date, datetime

from sqlalchemy import CHAR, Boolean, Date, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Committee(Base):
    __tablename__ = "committees"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    description: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class CommitteeMember(Base):
    __tablename__ = "committee_members"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    committee_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class BoardCommitteeChatMessage(Base):
    __tablename__ = "board_committee_chat"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    pool_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    pool_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    sender_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
