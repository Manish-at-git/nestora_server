"""Mappings for the legacy-compatible wallet tables used by the modular API."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CHAR, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"), unique=True, index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    reward_points: Mapped[int] = mapped_column(Integer, default=0)
    security_pin: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str | None] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("wallets.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str | None] = mapped_column(String(50), default="Completed")
    reference_number: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
