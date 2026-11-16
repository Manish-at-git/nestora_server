"""Persistence models for non-login association workers and their attendance."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StaffMember(Base):
    """A daily worker assigned to one association with a restricted login account."""

    __tablename__ = "staff_members"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("associations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    staff_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    designation: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_number: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    assignment_type: Mapped[str] = mapped_column(String(20), nullable=False, default="common_area", server_default="common_area")
    block_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("blocks.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    unit_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("units.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    account_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL"), unique=True, nullable=True, index=True
    )
    temp_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("location_cities.id", ondelete="RESTRICT"), nullable=True
    )
    pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    emergency_contact_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    id_proof_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_pic_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pass_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StaffAttendance(Base):
    """One physical arrival/departure record created from a staff member's QR pass."""

    __tablename__ = "staff_attendance"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    staff_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("staff_members.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    association_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("associations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True
    )
    checked_out_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True
    )
    gate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
