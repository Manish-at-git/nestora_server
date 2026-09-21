"""Request and response contracts for employee administration."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class EmployeeCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    address_line_1: str = Field(min_length=1, max_length=255)
    address_line_2: str | None = None
    city_id: str = Field(min_length=1, max_length=36)
    pincode: str = Field(min_length=1, max_length=20)
    email: EmailStr
    contact_number: str = Field(min_length=1, max_length=30)
    emergency_contact_name: str | None = None
    emergency_contact_number: str | None = None
    id_proof_url: str | None = None
    role_id: str
    association_ids: list[str] = Field(default_factory=list)
    onboard_date: date | None = None
    end_date: date | None = None

    @field_validator("onboard_date", "end_date", mode="before")
    @classmethod
    def blank_dates_are_none(cls, value):
        return None if value == "" else value


class EmployeeUpdateRequest(BaseModel):
    role_id: str
    association_ids: list[str] = Field(default_factory=list)
    onboard_date: date | None = None
    end_date: date | None = None

    @field_validator("onboard_date", "end_date", mode="before")
    @classmethod
    def blank_dates_are_none(cls, value):
        return None if value == "" else value


class EmployeeAssociationResponse(BaseModel):
    id: str
    name: str


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: str
    email: str
    role_id: str
    role_name: str | None = None
    employee_id_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None
    contact_number: str | None = None
    address: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city_id: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    onboard_date: date | None = None
    end_date: date | None = None
    emergency_contact_name: str | None = None
    emergency_contact_number: str | None = None
    id_proof_url: str | None = None
    temp_password: str | None = None
    associations: list[EmployeeAssociationResponse] = Field(default_factory=list)
    created_at: datetime | None = None


class EmployeeCreateResponse(BaseModel):
    ok: bool = True
    account_id: str
    temp_password: str


class EmployeeMutationResponse(BaseModel):
    ok: bool = True
