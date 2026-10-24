from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class DelinquencyStatus(StrEnum):
    RESOLVED = "resolved"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DelinquencyRowRequest(BaseModel):
    member_name: str = Field(min_length=1, max_length=255)
    unit_number: str = Field(min_length=1, max_length=100)
    block: str | None = Field(default=None, max_length=100)
    charge_category: str = Field(min_length=1, max_length=150)
    outstanding_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    days_overdue: int = Field(ge=0, le=36500)
    last_payment_date: date | None = None

    @field_validator("member_name", "unit_number", "charge_category")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("block")
    @classmethod
    def normalize_block(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else ""
        return cleaned or None


class DelinquencyReportRequest(BaseModel):
    association_id: str = Field(min_length=1, max_length=36)
    fiscal_period: str = Field(min_length=3, max_length=100)
    total_billed_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    total_collected_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    rows: list[DelinquencyRowRequest] = Field(min_length=1, max_length=2000)

    @field_validator("fiscal_period")
    @classmethod
    def fiscal_period_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("fiscal period must not be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_collection_and_rows(self) -> "DelinquencyReportRequest":
        if self.total_collected_amount > self.total_billed_amount:
            raise ValueError("total collected amount cannot exceed total billed amount")
        identities = [
            (row.member_name.casefold(), row.unit_number.casefold(), row.charge_category.casefold())
            for row in self.rows
        ]
        if len(identities) != len(set(identities)):
            raise ValueError(
                "member, unit, and charge category combinations must be unique"
            )
        return self


class DelinquencyRowResponse(DelinquencyRowRequest):
    id: str
    status: DelinquencyStatus


class DelinquencySummary(BaseModel):
    total_outstanding: Decimal
    delinquent_member_count: int
    row_count: int
    average_days_overdue: Decimal
    high_risk_count: int
    total_billed_amount: Decimal
    total_collected_amount: Decimal
    collection_rate_percentage: Decimal


class DelinquencyDistributionItem(BaseModel):
    name: str
    amount: Decimal
    percentage: Decimal
    row_count: int


class DelinquencyReportResponse(BaseModel):
    id: str
    association_id: str
    association_name: str
    fiscal_period: str
    applied_block: str | None = None
    applied_search: str | None = None
    available_blocks: list[str]
    rows: list[DelinquencyRowResponse]
    summary: DelinquencySummary
    charge_distribution: list[DelinquencyDistributionItem]
    aging_distribution: list[DelinquencyDistributionItem]
    insights: list[str]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DelinquencyMutationResponse(BaseModel):
    id: str
    imported_items: int | None = None
