import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Poll(Base):
    __tablename__ = "polls"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    question: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(50), default="All", server_default="All")
    status: Mapped[str] = mapped_column(String(50), default="Published", server_default="Published")
    is_multiple_choice: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    end_date: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(CHAR(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class PollOption(Base):
    __tablename__ = "poll_options"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    poll_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    option_text: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class PollVote(Base):
    __tablename__ = "poll_votes"
    poll_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    option_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class PollLike(Base):
    __tablename__ = "poll_likes"
    poll_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class PollComment(Base):
    __tablename__ = "poll_comments"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    poll_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
