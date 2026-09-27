"""Persistence model for the global Nearby Places catalogue."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CHAR,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NearbyPlace(Base):
    __tablename__ = "nearby_places"
    __table_args__ = (
        Index("ix_nearby_places_category", "category"),
        Index("ix_nearby_places_is_active", "is_active"),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    distance: Mapped[str] = mapped_column(
        String(100), nullable=False, default="0.5 km away", server_default="0.5 km away"
    )
    rating: Mapped[float] = mapped_column(
        Numeric(3, 1), nullable=False, default=4.8, server_default="4.8"
    )
    reviews: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Open", server_default="Open"
    )
    address: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
