"""IAM models for roles, manageable features, and per-role feature permissions."""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.entities.models import Entity


class Role(Base):
    """A system role such as super_admin or homeowner."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity = relationship(Entity, foreign_keys=[entity_id])
    feature_permissions = relationship("RoleFeaturePermission", back_populates="role")


class Feature(Base):
    """A manageable application capability that can be shown in one or more role sidebars."""

    __tablename__ = "features"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Some copied feature rows have no code. Preserve that distinction in the
    # static seed snapshot; future feature creation can require a code at the API layer.
    code: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("features.id", ondelete="SET NULL"), nullable=True, index=True
    )
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    route: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    role_permissions = relationship("RoleFeaturePermission", back_populates="feature")
    parent = relationship("Feature", remote_side="Feature.id", back_populates="children")
    children = relationship("Feature", back_populates="parent")


class RoleFeaturePermission(Base):
    """One role's CRUD access and sidebar position for one feature."""

    __tablename__ = "role_feature_permissions"
    __table_args__ = (UniqueConstraint("role_id", "feature_id", name="uq_role_feature_permissions_role_feature"),)

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("roles.id", ondelete="CASCADE"), index=True
    )
    feature_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("features.id", ondelete="CASCADE"), index=True
    )
    can_create: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_view: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_update: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    sidebar_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    role = relationship("Role", back_populates="feature_permissions")
    feature = relationship("Feature", back_populates="role_permissions")
