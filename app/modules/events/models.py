"""Persistence models for events and engagement rows."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(50))
    banner_url: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_registration_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    max_capacity: Mapped[int | None] = mapped_column()
    audience: Mapped[str] = mapped_column(String(50), default="All", server_default="All")
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    fee_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    organizer_name: Mapped[str | None] = mapped_column(String(100))
    organizer_contact: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="Published", server_default="Published")
    created_by: Mapped[str | None] = mapped_column(CHAR(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class EventRSVP(Base):
    __tablename__ = "event_rsvps"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="going")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class EventLike(Base):
    __tablename__ = "event_likes"
    event_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class EventComment(Base):
    __tablename__ = "event_comments"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
