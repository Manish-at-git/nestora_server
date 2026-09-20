"""Pydantic contracts for amenities and reservations."""

from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.responses import ApiResponse
from app.modules.amenities.constants import AmenityPaymentMethod


class AmenityCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    charges: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    status: bool = True

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Amenity name cannot be blank")
        return value


class AmenityStatusRequest(BaseModel):
    status: bool


class AmenityBookingRequest(BaseModel):
    booking_date: date
    start_time: time
    end_time: time
    duration_hours: int = Field(gt=0, le=24)
    payment_method: AmenityPaymentMethod = AmenityPaymentMethod.WALLET
    pin: str | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "AmenityBookingRequest":
        if self.end_time <= self.start_time:
            raise ValueError("Booking end time must be after start time")
        if self.payment_method == AmenityPaymentMethod.WALLET and not self.pin:
            raise ValueError("Wallet PIN is required")
        return self


class AmenityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    association_id: str
    association_name: str | None = None
    name: str
    charges: Decimal | None = None
    status: bool
    created_at: datetime | None = None


class AmenityBookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    amenity_id: str
    amenity_name: str | None = None
    association_id: str
    association_name: str | None = None
    user_id: str
    homeowner_name: str | None = None
    unit_number: str | None = None
    contact_no: str | None = None
    amount: Decimal | None = None
    booking_date: date
    payment_status: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_hours: int | None = None
    created_at: datetime | None = None


class AmenitySlotResponse(BaseModel):
    booking_date: date
    start_time: time | None = None
    end_time: time | None = None
    duration_hours: int | None = None
    homeowner_name: str | None = None
    unit_number: str | None = None


class AmenityCreateResponse(BaseModel):
    id: str


class AmenityBookingCreateResponse(BaseModel):
    booking_id: str


class AmenityMutationResponse(BaseModel):
    updated: bool = True


AmenityListResponse = ApiResponse[list[AmenityResponse]]
AmenityBookingListResponse = ApiResponse[list[AmenityBookingResponse]]

