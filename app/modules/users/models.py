"""Persistence models for resident/user profiles and activation codes."""

import uuid
from datetime import date, datetime

from sqlalchemy import CHAR, Boolean, Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserCode(Base):
    __tablename__ = "user_codes"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    login_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserDetail(Base):
    __tablename__ = "user_details"

    user_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("user_codes.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_number: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    unit_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    emergency_contact_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    id_proof_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    onboard_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    board_member_since: Mapped[date | None] = mapped_column(Date, nullable=True)
    profile_pic_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_id: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("roles.id"), nullable=True, index=True)
    association_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
