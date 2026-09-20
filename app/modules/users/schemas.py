"""Request and response contracts for system users."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    contact_number: str = Field(min_length=1, max_length=30)
    role_id: str
    association_id: str


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    contact_number: str | None = None
    association_id: str | None = None
    block_name: str | None = None
    unit_number: str | None = None
    role_name: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None
    contact_number: str | None = None
    email: str | None = None
    account_id: str | None = None
    activation_code: str | None = None
    activation_status: str | None = None
    role_name: str | None = None
    unit_id: str | None = None
    block_id: str | None = None
    association_id: str | None = None
    association_name: str | None = None
    block_name: str | None = None
    unit_number: str | None = None
    assoc_addr1: str | None = None
    assoc_addr2: str | None = None
    assoc_city: str | None = None
    assoc_state: str | None = None
    assoc_pincode: str | None = None
    created_at: datetime | None = None


class UserCreateResponse(BaseModel):
    ok: bool = True
    message: str
    activation_code: str


class UserMutationResponse(BaseModel):
    ok: bool = True
    message: str
