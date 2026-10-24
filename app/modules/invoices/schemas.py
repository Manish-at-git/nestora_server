from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class InvoiceStatus(StrEnum):
    PAID = "paid"
    PENDING = "pending"
    OVERDUE = "overdue"


class InvoiceRequest(BaseModel):
    association_id: str = Field(min_length=1, max_length=36)
    invoice_number: str = Field(min_length=1, max_length=100)
    vendor_name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    invoice_date: date
    due_date: date
    subtotal: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    tax_percentage: Decimal = Field(default=Decimal("0"), ge=0, max_digits=7, decimal_places=2)
    status: InvoiceStatus = InvoiceStatus.PENDING
    payment_date: date | None = None
    payment_method: str | None = Field(default=None, max_length=100)

    @field_validator("invoice_number", "vendor_name", "category")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_dates_and_payment(self):
        if self.due_date < self.invoice_date:
            raise ValueError("due date cannot be before invoice date")
        if self.status == InvoiceStatus.PAID and not self.payment_date:
            raise ValueError("payment date is required for paid invoices")
        return self


class InvoiceResponse(BaseModel):
    id: str
    association_id: str
    association_name: str
    invoice_number: str
    vendor_name: str
    category: str
    description: str | None
    invoice_date: date
    due_date: date
    subtotal: Decimal
    tax_percentage: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: InvoiceStatus
    payment_date: date | None
    payment_method: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InvoiceListResponse(BaseModel):
    rows: list[InvoiceResponse]
    total_count: int
    total_amount: Decimal
    paid_amount: Decimal
    pending_amount: Decimal
    overdue_amount: Decimal
    available_categories: list[str]
