"""Persistence models for entity type classifications."""

from datetime import datetime

from sqlalchemy import Boolean, CHAR, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EntityType(Base):
    """A reusable classification such as HOA, condominium, or co-op."""

    __tablename__ = "entity_types"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0", default=False)
