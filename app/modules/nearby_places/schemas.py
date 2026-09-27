"""Validated request and response contracts for Nearby Places."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.nearby_places.constants import NEARBY_CATEGORY_CODES


class NearbyPlaceFields(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    distance: str = Field(default="0.5 km away", min_length=1, max_length=100)
    rating: Decimal = Field(
        default=Decimal("4.8"), ge=1, le=5, max_digits=3, decimal_places=1
    )
    reviews: int = Field(default=0, ge=0)
    status: str = Field(default="Open", min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=5000)
    phone: str | None = Field(default=None, max_length=100)
    image: str | None = Field(default=None, max_length=5000)
    tags: str | None = Field(default=None, max_length=5000)
    website: str | None = Field(default=None, max_length=5000)
    is_active: bool = True

    @field_validator("name", "distance", "status", "address")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field is required")
        return normalized

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in NEARBY_CATEGORY_CODES:
            raise ValueError("Select a valid nearby place category")
        return normalized

    @field_validator("phone", "image", "tags", "website")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class NearbyPlaceCreate(NearbyPlaceFields):
    pass


class NearbyPlaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    distance: str | None = Field(default=None, min_length=1, max_length=100)
    rating: Decimal | None = Field(
        default=None, ge=1, le=5, max_digits=3, decimal_places=1
    )
    reviews: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = Field(default=None, min_length=1, max_length=5000)
    phone: str | None = Field(default=None, max_length=100)
    image: str | None = Field(default=None, max_length=5000)
    tags: str | None = Field(default=None, max_length=5000)
    website: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None

    @field_validator("name", "distance", "status", "address")
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field is required")
        return normalized

    @field_validator("category")
    @classmethod
    def validate_optional_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in NEARBY_CATEGORY_CODES:
            raise ValueError("Select a valid nearby place category")
        return normalized

    @field_validator("phone", "image", "tags", "website")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class NearbyPlaceResponse(NearbyPlaceFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NearbyPlaceMutationResponse(BaseModel):
    ok: bool = True
    message: str
