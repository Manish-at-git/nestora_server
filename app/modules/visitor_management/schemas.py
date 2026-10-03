"""Request and response contracts for visitor management."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    number_of_visitors: int = Field(ge=1, le=100)
    vehicle_number: str | None = None
    purpose: str | None = None
    pass_type: str = Field(default="Single Entry", max_length=50)

    @model_validator(mode="after")
    def validate_schedule(self) -> "PreApprovedVisitorRequest":
        if datetime.combine(self.visit_date, self.start_time) <= datetime.now():
            raise ValueError("Visit date and start time must be in the future")
        if self.end_time <= self.start_time:
            raise ValueError("End time must be later than start time")
        return self


class CheckInRequest(BaseModel):
    otp: str | None = Field(default=None, min_length=4, max_length=10)
    gate: str | None = None
    visitor_photo_url: str | None = None
    remarks: str | None = None


class WalkInCheckInRequest(BaseModel):
    gate: str | None = Field(default=None, max_length=50)


class VisitorCheckOutRequest(BaseModel):
    remarks: str | None = Field(default=None, max_length=500)


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
