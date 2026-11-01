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
    effective_subscription_status: str = "Active"
    subscription_start: date | None = None
    subscription_end: date | None = None
    renewal_date: date | None = None
    payment_status: str | None = None
    trial_days: int = 0
    trial_days_left: int = 0
    trial_display: str = "No trial"
    is_trial_expired: bool = False
    subscription_days_left: int | None = None
    subscription_expiry_display: str = "No end date"
    is_subscription_expired: bool = False
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

    @field_validator("subscription_status")
    @classmethod
    def normalize_subscription_status(cls, value: str | None) -> str | None:
        """Only Active and Inactive are administrator-controlled statuses."""
        if value is None:
            return None
        normalized = value.strip().casefold()
        if normalized == "active":
            return "Active"
        if normalized in {"inactive", "cancelled", "canceled"}:
            return "Inactive"
        raise ValueError("Subscription status must be Active or Inactive")


class AssessmentRules(BaseModel):
    frequency: str = Field(min_length=1, max_length=50)
    default_amount: float = Field(ge=0)
    due_day_of_month: int = Field(ge=1, le=31)
    is_advanced_enabled: bool = False
    owner_occupied_amount: float | None = Field(default=None, ge=0)
    rented_amount: float | None = Field(default=None, ge=0)


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


class UnitOccupancyUpdateRequest(BaseModel):
    is_rented: bool


class AssociationUnitResponse(BaseModel):
    id: str
    unit_number: str
    block_name: str | None = None
    is_rented: bool = False


class AssociationOnboardResponse(BaseModel):
    ok: bool = True
    association_id: str
    homeowners_created: int
    tenants_created: int
    units_created: int
    committees_created: int
