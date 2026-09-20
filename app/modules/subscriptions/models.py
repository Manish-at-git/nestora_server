"""Subscription plan and plan-feature persistence models."""

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.iam.models import Feature


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    country: Mapped[str] = mapped_column(String(10), nullable=False, default="IN")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    yearly_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    feature_assignments = relationship(
        "SubscriptionPlanFeature", back_populates="plan", cascade="all, delete-orphan"
    )


class SubscriptionPlanFeature(Base):
    __tablename__ = "subscription_plan_features"
    __table_args__ = (UniqueConstraint("plan_id", "feature_id", name="uq_subscription_plan_feature"),)

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("subscription_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("features.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plan = relationship(SubscriptionPlan, back_populates="feature_assignments")
    feature = relationship(Feature)
