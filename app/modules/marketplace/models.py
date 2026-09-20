"""Persistence models for marketplace records and engagement."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CHAR, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketplaceCategory(Base):
    __tablename__ = "marketplace_categories"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class MarketplaceItem(Base):
    __tablename__ = "marketplace_items"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    association_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("associations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("marketplace_categories.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    condition_state: Mapped[str | None] = mapped_column(String(50))
    brand: Mapped[str | None] = mapped_column(String(100))
    item_age: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(100))
    contact_number: Mapped[str | None] = mapped_column(String(30))
    is_negotiable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    status: Mapped[str | None] = mapped_column(String(20), default="Active", server_default="Active")
    listing_type: Mapped[str | None] = mapped_column(String(50), default="Sell", server_default="Sell")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class MarketplaceImage(Base):
    __tablename__ = "marketplace_images"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("marketplace_items.id", ondelete="CASCADE"), index=True)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class MarketplaceFavorite(Base):
    __tablename__ = "marketplace_favorites"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("marketplace_items.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class MarketplaceChatMessage(Base):
    __tablename__ = "marketplace_chat"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("marketplace_items.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"))
    receiver_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class MarketplaceReport(Base):
    __tablename__ = "marketplace_reports"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("marketplace_items.id", ondelete="CASCADE"), index=True)
    reporter_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class MarketplaceView(Base):
    __tablename__ = "marketplace_views"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("marketplace_items.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("accounts.account_id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
