"""Validated subscription plan request and response contracts."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class SubscriptionPlanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    country: str = Field(default="IN", min_length=2, max_length=10)
    description: str | None = Field(default=None, max_length=65535)
    monthly_price: Decimal | None = Field(default=None, ge=0)
    yearly_price: Decimal | None = Field(default=None, ge=0)
    trial_days: int = Field(default=0, ge=0)
    is_active: bool = True

    @field_validator("name", "code", "country", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.upper()


class SubscriptionPlanResponse(BaseModel):
    id: str
    name: str
    code: str | None = None
    country: str
    description: str | None = None
    monthly_price: Decimal | None = None
    yearly_price: Decimal | None = None
    trial_days: int
    is_active: bool
    features: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PlanFeatureRequest(BaseModel):
    feature_ids: list[str] = []


class MutationResponse(BaseModel):
    ok: bool = True
