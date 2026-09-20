"""Persistence models for service-request tickets and their message threads."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Legacy rows can point either to accounts.account_id or user_details.user_id,
    # so this intentionally remains a polymorphic identifier without a foreign key.
    user_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    association_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    unit_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    sr_display_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    service_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sub_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="New", server_default="Pending"
    )
    incoming_call_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ServiceRequestThreadMessage(Base):
    __tablename__ = "service_request_messages"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    service_request_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("service_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False, index=True
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
