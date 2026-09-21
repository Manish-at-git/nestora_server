"""Association list, statistics, and subscription contracts."""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class AssociationResponse(BaseModel):
    id: str
    name: str
    association_code: str | None = None
    entity_id: str | None = None
    entity_name: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city_id: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None
    url: str | None = None
    association_url: str | None = None
    contract_url: str | None = None
    current_plan_id: str | None = None
    plan_name: str | None = None
    subscription_status: str | None = None
    subscription_start: date | None = None
    subscription_end: date | None = None
    renewal_date: date | None = None
    payment_status: str | None = None
    unit_count: int = 0
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    allowed_features: list[str] = []


class AssociationStats(BaseModel):
    name: str
    contract_url: str | None = None
    total_blocks: int = 0
    total_units: int = 0
    rented_units: int = 0
    floors_per_block: list[dict] = []


class AssociationSubscriptionRequest(BaseModel):
    plan_id: str | None = None
    subscription_start: date | None = None
    subscription_end: date | None = None
    payment_status: str | None = None
    renewal_date: date | None = None
    subscription_status: str | None = None

    @field_validator("plan_id", "subscription_start", "subscription_end", "renewal_date", mode="before")
    @classmethod
    def blank_values_are_none(cls, value):
        """HTML forms submit empty date/select fields as empty strings."""
        return None if value == "" else value


class AssessmentRules(BaseModel):
    frequency: str = Field(min_length=1, max_length=50)
    default_amount: float = Field(ge=0)
    due_day_of_month: int = Field(ge=1, le=31)


class FineRule(BaseModel):
    id: str | None = None
    fine_type: str = Field(min_length=1, max_length=100)
    amount: float = Field(ge=0)
    grace_period_days: int = Field(ge=0)


class AssociationSettingsResponse(BaseModel):
    onboarding_date: date | None = None
    end_date: date | None = None
    assessment_rules: AssessmentRules | None = None
    fine_rules: list[FineRule] = Field(default_factory=list)


class AssociationSettingsUpdateRequest(BaseModel):
    end_date: date | None = None
    assessment_rules: AssessmentRules | None = None
    fine_rules: list[FineRule] | None = None

    @field_validator("end_date", mode="before")
    @classmethod
    def blank_end_date_is_none(cls, value):
        return None if value == "" else value


class MutationResponse(BaseModel):
    ok: bool = True


class AssociationOnboardResponse(BaseModel):
    ok: bool = True
    association_id: str
    homeowners_created: int
    tenants_created: int
    units_created: int
    committees_created: int
