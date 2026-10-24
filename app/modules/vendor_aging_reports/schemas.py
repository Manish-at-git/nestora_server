from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class VendorAgingStatus(StrEnum):
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    SETTLED = "settled"


class VendorAgingRowRequest(BaseModel):
    vendor_name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=150)
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: date
    current_due: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    days_1_30: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    days_31_60: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    days_61_90: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    days_over_90: Decimal = Field(ge=0, max_digits=18, decimal_places=2)

    @field_validator("vendor_name", "category", "invoice_number")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class VendorAgingReportRequest(BaseModel):
    association_id: str = Field(min_length=1, max_length=36)
    fiscal_period: str = Field(min_length=3, max_length=100)
    rows: list[VendorAgingRowRequest] = Field(min_length=1, max_length=2000)

    @field_validator("fiscal_period")
    @classmethod
    def fiscal_period_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("fiscal period must not be blank")
        return cleaned

    @model_validator(mode="after")
    def invoices_must_be_unique_per_vendor(self) -> "VendorAgingReportRequest":
        identities = [
            (row.vendor_name.casefold(), row.invoice_number.casefold())
            for row in self.rows
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("invoice numbers must be unique for each vendor")
        return self


class VendorAgingRowResponse(VendorAgingRowRequest):
    id: str
    total_outstanding: Decimal
    overdue_amount: Decimal
    status: VendorAgingStatus


class VendorAgingSummary(BaseModel):
    vendor_count: int
    invoice_count: int
    total_outstanding: Decimal
    overdue_amount: Decimal
    current_amount: Decimal
    overdue_percentage: Decimal
    overdue_invoice_count: int


class VendorAgingDistributionItem(BaseModel):
    name: str
    amount: Decimal
    percentage: Decimal
    invoice_count: int


class VendorAgingReportResponse(BaseModel):
    id: str
    association_id: str
    association_name: str
    fiscal_period: str
    applied_category: str | None = None
    applied_search: str | None = None
    available_categories: list[str]
    rows: list[VendorAgingRowResponse]
    summary: VendorAgingSummary
    aging_distribution: list[VendorAgingDistributionItem]
    category_distribution: list[VendorAgingDistributionItem]
    insights: list[str]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class VendorAgingMutationResponse(BaseModel):
    id: str
    imported_items: int | None = None
