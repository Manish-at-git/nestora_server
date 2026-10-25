from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class InvoiceStatus(StrEnum):
    PENDING = "pending"
    OVERDUE = "overdue"
    PAID = "paid"
    CANCELLED = "cancelled"


class DiscountType(StrEnum):
    NONE = "none"
    FLAT = "flat"
    PERCENTAGE = "percentage"


class InvoiceLineRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    rate: Decimal = Field(ge=0, max_digits=18, decimal_places=2)

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class InvoiceRequest(BaseModel):
    association_id: str = Field(min_length=1, max_length=36)
    vendor_id: str = Field(min_length=1, max_length=36)
    billing_address: str = Field(min_length=1, max_length=2000)
    invoice_number: str | None = Field(default=None, max_length=100)
    issue_date: date
    due_date: date
    payment_terms: str = Field(min_length=1, max_length=255)
    lines: list[InvoiceLineRequest] = Field(min_length=1, max_length=500)
    discount_type: DiscountType = DiscountType.NONE
    discount_value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    tax_type: str | None = Field(default=None, max_length=100)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=7, decimal_places=2)
    notes: str | None = Field(default=None, max_length=4000)
    status: InvoiceStatus = InvoiceStatus.PENDING
    payment_date: date | None = None
    payment_method: str | None = Field(default=None, max_length=100)

    @field_validator("billing_address", "payment_terms")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("invoice_number")
    @classmethod
    def normalize_invoice_number(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None

    @model_validator(mode="after")
    def validate_business_rules(self):
        if self.due_date < self.issue_date:
            raise ValueError("due date cannot be before issue date")
        if self.discount_type == DiscountType.NONE and self.discount_value != 0:
            raise ValueError("discount value must be zero when discount type is none")
        if self.discount_type == DiscountType.PERCENTAGE and self.discount_value > 100:
            raise ValueError("percentage discount cannot exceed 100")
        if self.status == InvoiceStatus.PAID and not self.payment_date:
            raise ValueError("payment date is required for paid invoices")
        if self.payment_date and self.payment_date < self.issue_date:
            raise ValueError("payment date cannot be before issue date")
        return self


class InvoiceStatusRequest(BaseModel):
    association_id: str = Field(min_length=1, max_length=36)
    status: InvoiceStatus
    payment_date: date | None = None
    payment_method: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def paid_status_requires_date(self):
        if self.status == InvoiceStatus.PAID and not self.payment_date:
            raise ValueError("payment date is required for paid invoices")
        return self


class InvoiceLineResponse(BaseModel):
    id: str
    description: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    sort_order: int


class InvoicePaymentAccountResponse(BaseModel):
    bank_name: str
    account_number: str
    ifsc_code: str


class InvoiceResponse(BaseModel):
    id: str
    association_id: str
    association_name: str
    vendor_id: str | None
    vendor_name: str
    vendor_service: str
    payment_account: InvoicePaymentAccountResponse | None
    billing_address: str | None
    invoice_number: str
    issue_date: date
    due_date: date
    fiscal_period: str
    payment_terms: str | None
    lines: list[InvoiceLineResponse]
    discount_type: DiscountType
    discount_value: Decimal
    tax_type: str | None
    tax_rate: Decimal
    notes: str | None
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    grand_total: Decimal
    status: InvoiceStatus
    payment_date: date | None
    payment_method: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InvoiceListResponse(BaseModel):
    rows: list[InvoiceResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    total_amount: Decimal
    paid_amount: Decimal
    pending_amount: Decimal
    overdue_amount: Decimal
    available_fiscal_periods: list[str]


class InvoiceVendorResponse(BaseModel):
    id: str
    name: str
    service_type: str
    payment_terms: str | None
    payment_account: InvoicePaymentAccountResponse | None


class InvoiceMutationResponse(BaseModel):
    id: str
