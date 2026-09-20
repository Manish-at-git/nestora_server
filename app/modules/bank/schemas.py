"""Request and response contracts for bank account CRUD."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BankAccountRequest(BaseModel):
    association_id: str
    account_name: str = Field(min_length=1, max_length=255)
    account_holder_name: str = Field(min_length=1, max_length=255)
    bank_name: str = Field(min_length=1, max_length=255)
    account_number: str = Field(min_length=1)
    ifsc_code: str = Field(min_length=1, max_length=50)
    branch_name: str | None = None
    account_type: str = "Current"
    currency: str = "INR"
    upi_id: str | None = None
    qr_code_url: str | None = None
    gateway_provider: str | None = None
    merchant_id: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    webhook_secret: str | None = None
    is_default: bool = False
    status: str = "Active"

    @field_validator("account_number")
    @classmethod
    def account_number_must_be_numeric(cls, value: str) -> str:
        """Keep account numbers numeric while allowing masked edit responses."""
        if value.startswith("****"):
            return value
        if not value.isdigit():
            raise ValueError("Account number must contain digits only")
        return value


class BankAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    association_id: str
    association_name: str | None = None
    account_name: str
    account_holder_name: str
    bank_name: str
    account_number: str
    ifsc_code: str
    branch_name: str | None = None
    account_type: str
    currency: str
    upi_id: str | None = None
    qr_code_url: str | None = None
    gateway_provider: str | None = None
    merchant_id: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    webhook_secret: str | None = None
    is_default: bool
    status: str
    created_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None


class BankAccountMutationResponse(BaseModel):
    ok: bool = True
    id: str | None = None
