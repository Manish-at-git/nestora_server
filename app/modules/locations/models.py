"""Normalized reference geography models.

The hierarchy is Country -> Region -> District -> City.  A city keeps its
region reference because some countries do not use districts consistently;
when it has a district, the country and region are derived from that district.
"""

import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Country(Base):
    __tablename__ = "location_countries"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    iso2_code: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)
    iso3_code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Region(Base):
    __tablename__ = "location_regions"
    __table_args__ = (
        UniqueConstraint("country_id", "code", name="uq_location_regions_country_code"),
        Index("ix_location_regions_country_id", "country_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    country_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("location_countries.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="STATE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    country = relationship(Country, lazy="joined")


class District(Base):
    __tablename__ = "location_districts"
    __table_args__ = (
        UniqueConstraint("region_id", "code", name="uq_location_districts_region_code"),
        Index("ix_location_districts_region_id", "region_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    region_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("location_regions.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="DISTRICT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class City(Base):
    __tablename__ = "location_cities"
    __table_args__ = (
        UniqueConstraint("region_id", "district_id", "name", name="uq_location_cities_region_district_name"),
        Index("ix_location_cities_region_id", "region_id"),
        Index("ix_location_cities_district_id", "district_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    region_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("location_regions.id", ondelete="RESTRICT"), nullable=False)
    district_id: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("location_districts.id", ondelete="RESTRICT"), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    region = relationship(Region, lazy="joined")
