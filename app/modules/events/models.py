"""Persistence models for events and engagement rows."""

import uuid
from datetime import datetime

from decimal import Decimal

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
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
    has_pass: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    pass_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    max_passes_per_user: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
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


class EventPass(Base):
    __tablename__ = "event_passes"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_name: Mapped[str | None] = mapped_column(String(150))
    buyer_mobile: Mapped[str | None] = mapped_column(String(50), index=True)
    total_passes: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    remaining_passes: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    checked_in_passes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    pass_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    qr_data: Mapped[str | None] = mapped_column(Text)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"), server_default="0.00")
    payment_method: Mapped[str | None] = mapped_column(String(50), default="wallet", server_default="wallet")
    payment_status: Mapped[str | None] = mapped_column(String(50), default="Completed", server_default="Completed")
    status: Mapped[str | None] = mapped_column(String(50), default="Active", server_default="Active")
    shared_from_pass_id: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("event_passes.id", ondelete="CASCADE"))
    shared_to_mobile: Mapped[str | None] = mapped_column(String(50))
    last_checked_in_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_checked_in_by: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class EventPassTransfer(Base):
    __tablename__ = "event_pass_transfers"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_pass_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("event_passes.id", ondelete="CASCADE"), nullable=False, index=True)
    new_pass_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("event_passes.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_account_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(150))
    sender_mobile: Mapped[str | None] = mapped_column(String(50))
    recipient_mobile: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(150))
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EventPassCheckIn(Base):
    __tablename__ = "event_pass_checkins"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pass_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("event_passes.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    admitted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    checked_in_by: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL"))
    checked_in_by_name: Mapped[str | None] = mapped_column(String(150))
    notes: Mapped[str | None] = mapped_column(Text)
    checked_in_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
