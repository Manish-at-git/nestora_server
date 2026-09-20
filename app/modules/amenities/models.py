"""Persistence models for amenities and amenity bookings."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import CHAR, Boolean, Date, DateTime, Integer, Numeric, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Amenity(Base):
    __tablename__ = "amenities"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    charges: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True, default=Decimal("0"))
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class AmenityBooking(Base):
    __tablename__ = "amenity_bookings"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    amenity_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    association_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    unit_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    homeowner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True, default=Decimal("0"))
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_status: Mapped[str | None] = mapped_column(String(50), nullable=True, default="Pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

