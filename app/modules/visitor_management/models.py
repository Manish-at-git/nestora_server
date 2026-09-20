"""SQLAlchemy metadata for legacy visitor-management tables."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, CHAR, Date, DateTime, Integer, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Visitor(Base):
    __tablename__ = "visitors"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    mobile: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    photo_url: Mapped[str | None] = mapped_column(String(255))
    id_type: Mapped[str | None] = mapped_column(String(50))
    id_number: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(255))
    emergency_contact: Mapped[str | None] = mapped_column(String(30))
    police_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    id_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    status: Mapped[str | None] = mapped_column(String(30), default="Active", server_default="Active")
    pass_expiry_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class VisitorVisit(Base):
    __tablename__ = "visitor_visits"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    visitor_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    unit_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    purpose: Mapped[str | None] = mapped_column(String(255))
    visitor_type: Mapped[str | None] = mapped_column(String(50))
    number_of_visitors: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    vehicle_number: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    expected_duration: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="Pending", server_default="Pending")
    pass_code: Mapped[str | None] = mapped_column(String(50))
    check_in_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_out_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class PreApprovedVisitor(Base):
    __tablename__ = "pre_approved_visitors"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resident_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    unit_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    visitor_name: Mapped[str] = mapped_column(String(150), nullable=False)
    mobile: Mapped[str] = mapped_column(String(20), nullable=False)
    visitor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    pass_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    otp: Mapped[str | None] = mapped_column(String(10))
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    number_of_visitors: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    vehicle_number: Mapped[str | None] = mapped_column(String(50))
    purpose: Mapped[str | None] = mapped_column(String(255))
    pass_type: Mapped[str | None] = mapped_column(String(50), default="Single Entry", server_default="Single Entry")
    status: Mapped[str] = mapped_column(String(30), default="Active", server_default="Active")
    created_by: Mapped[str | None] = mapped_column(CHAR(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class VisitorLog(Base):
    __tablename__ = "visitor_logs"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pre_approved_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    check_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gate: Mapped[str | None] = mapped_column(String(50))
    guard_id: Mapped[str | None] = mapped_column(CHAR(36))
    visitor_photo_url: Mapped[str | None] = mapped_column(String(255))
    remarks: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    unit_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    resident_id: Mapped[str | None] = mapped_column(CHAR(36))
    delivery_type: Mapped[str] = mapped_column(String(30), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(150))
    delivery_person_name: Mapped[str | None] = mapped_column(String(150))
    mobile: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    gate: Mapped[str | None] = mapped_column(String(50))
    guard_id: Mapped[str | None] = mapped_column(CHAR(36))
    package_photo_url: Mapped[str | None] = mapped_column(String(255))
    check_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(50))
    registration_number: Mapped[str] = mapped_column(String(50), nullable=False)
    insurance_url: Mapped[str | None] = mapped_column(String(255))
    puc_url: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
