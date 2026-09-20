"""Persistence model for manageable business entities."""

from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.entity_types.models import EntityType


class Entity(Base):
    """A business entity classified by an entity type."""

    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    entity_type_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("entity_types.id", ondelete="SET NULL"), nullable=True, index=True
    )
    association_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0", default=False
    )

    entity_type = relationship(EntityType, lazy="joined")
