"""Persistence model for association operating bank accounts."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BankAccount(Base):
    __tablename__ = "association_bank_accounts"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("associations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_holder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_number: Mapped[str] = mapped_column(Text, nullable=False)
    ifsc_code: Mapped[str] = mapped_column(String(50), nullable=False)
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Current")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    upi_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qr_code_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gateway_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    merchant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active", server_default="Active")
    created_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    association = relationship("Association", foreign_keys=[association_id], lazy="joined")
