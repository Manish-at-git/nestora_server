"""Persistence mappings for violations and participant messages."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ViolationSequence(Base):
    __tablename__ = "violation_sequences"

    association_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    next_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Violation(Base):
    __tablename__ = "violations"
    __table_args__ = (UniqueConstraint("association_id", "sequence_number", name="uq_violations_association_sequence"),)

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Display IDs are association-scoped; the composite sequence is the unique contract.
    display_id: Mapped[str] = mapped_column(String(32), nullable=False)
    reporter_account_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id"), nullable=False, index=True)
    reporter_unit_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    knows_violator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    violator_user_id: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("user_details.user_id"), nullable=True, index=True)
    violator_account_id: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("accounts.account_id"), nullable=True, index=True)
    violator_unit_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    incident_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    proof_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="New")
    offense_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fine_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fine_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fine_transaction_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, unique=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    board_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    violator_response: Mapped[str | None] = mapped_column(String(64), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ViolationThreadMessage(Base):
    __tablename__ = "violation_messages"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    violation_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("violations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_account_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id"), nullable=False, index=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
