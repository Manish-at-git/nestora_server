from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class PrepaidStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"


class PrepaidReportRowRequest(BaseModel):
    member_name: str = Field(min_length=1, max_length=255)
    unit_number: str = Field(min_length=1, max_length=100)
    block: str | None = Field(default=None, max_length=100)
    category: str = Field(min_length=1, max_length=150)
    prepaid_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    used_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    expiry_date: date

    @field_validator("member_name", "unit_number", "category")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("block")
    @classmethod
    def normalize_optional_block(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def used_does_not_exceed_prepaid(self) -> "PrepaidReportRowRequest":
        if self.used_amount > self.prepaid_amount:
            raise ValueError("used amount cannot exceed prepaid amount")
        return self


class PrepaidReportRequest(BaseModel):
    association_id: str = Field(min_length=1, max_length=36)
    fiscal_period: str = Field(min_length=3, max_length=100)
    rows: list[PrepaidReportRowRequest] = Field(min_length=1, max_length=2000)

    @field_validator("fiscal_period")
    @classmethod
    def fiscal_period_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("fiscal period must not be blank")
        return cleaned


class PrepaidReportRowResponse(PrepaidReportRowRequest):
    id: str
    available_balance: Decimal
    status: PrepaidStatus


class PrepaidReportSummary(BaseModel):
    total_prepaid_amount: Decimal
    total_used_amount: Decimal
    total_available_balance: Decimal
    member_count: int
    average_prepaid_amount: Decimal
    utilization_pct: Decimal
    active_count: int
    expired_count: int


class PrepaidDistributionItem(BaseModel):
    name: str
    amount: Decimal
    percentage: Decimal
    row_count: int


class PrepaidReportResponse(BaseModel):
    id: str
    association_id: str
    association_name: str
    fiscal_period: str
    applied_block: str | None = None
    available_blocks: list[str]
    rows: list[PrepaidReportRowResponse]
    summary: PrepaidReportSummary
    category_distribution: list[PrepaidDistributionItem]
    status_distribution: list[PrepaidDistributionItem]
    insights: list[str]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PrepaidReportMutationResponse(BaseModel):
    id: str
    imported_items: int | None = None
