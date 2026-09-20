"""Request and response contracts for visitor management."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field


class VisitorRequest(BaseModel):
    mobile: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=150)
    visitor_type: str = Field(min_length=1, max_length=50)
    number_of_visitors: int = Field(default=1, ge=1, le=100)
    vehicle_number: str | None = None
    photo_url: str | None = None
    id_type: str | None = None
    id_number: str | None = None
    unit_id: str
    purpose: str = Field(min_length=1, max_length=255)
    expected_duration: str | None = None
    notes: str | None = None


class PreApprovedVisitorRequest(BaseModel):
    visitor_name: str = Field(min_length=1, max_length=150)
    mobile: str = Field(min_length=1, max_length=20)
    visitor_type: str = Field(min_length=1, max_length=50)
    visit_date: date
    start_time: time
    end_time: time
    number_of_visitors: int = Field(default=1, ge=1, le=100)
    vehicle_number: str | None = None
    purpose: str | None = None
    pass_type: str = Field(default="Single Entry", max_length=50)


class CheckInRequest(BaseModel):
    gate: str | None = None
    guard_id: str | None = None
    visitor_photo_url: str | None = None
    remarks: str | None = None


class DeliveryRequest(BaseModel):
    unit_id: str
    delivery_type: str = Field(min_length=1, max_length=30)
    company_name: str | None = None
    delivery_person_name: str | None = None
    mobile: str | None = None
    status: str = Field(default="Inside Premises", max_length=30)
    gate: str | None = None
    package_photo_url: str | None = None


class MutationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str | None = None
    ok: bool = True
    message: str | None = None
    pass_code: str | None = None
    otp: str | None = None
    log_id: str | None = None

