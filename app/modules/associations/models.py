"""Association directory persistence model."""

from datetime import date, datetime

from sqlalchemy import CHAR, Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.entities.models import Entity
from app.modules.locations.models import City
from app.modules.subscriptions.models import SubscriptionPlan


class Association(Base):
    __tablename__ = "associations"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    association_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("entities.id"), nullable=True)
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city_id: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("location_cities.id", ondelete="RESTRICT"), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_plan_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("subscription_plans.id", ondelete="SET NULL"), nullable=True
    )
    subscription_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subscription_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    subscription_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    entity = relationship(Entity, foreign_keys=[entity_id], lazy="joined")
    plan = relationship(SubscriptionPlan, foreign_keys=[current_plan_id], lazy="joined")
    location_city = relationship(City, foreign_keys=[city_id], lazy="joined")
