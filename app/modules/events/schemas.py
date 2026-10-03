from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.responses import ApiResponse
from app.core.validation import is_phone_number
from app.modules.events.constants import RSVPStatus


class EventCreateRequest(BaseModel):
    association_id: str | None = None
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    category: str | None = None
    banner_url: str | None = None
    location: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    is_registration_required: bool = False
    registration_deadline: datetime | None = None
    max_capacity: int | None = Field(default=None, ge=1)
    audience: str = "All"
    send_notifications: bool = False
    is_paid: bool = False
    fee_amount: Decimal | None = Field(default=None, ge=0)
    has_pass: bool = False
    pass_price: Decimal | None = Field(default=None, ge=0)
    max_passes_per_user: int = Field(default=10, ge=1, le=50)
    organizer_name: str | None = None
    organizer_contact: str | None = None
    status: str = "Published"

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_pass_settings(self) -> "EventCreateRequest":
        if self.has_pass and not self.is_paid:
            raise ValueError("Digital passes require a paid event.")
        if self.has_pass and (self.pass_price or self.fee_amount or 0) <= 0:
            raise ValueError("A digital pass must have a price greater than zero.")
        if self.has_pass and self.pass_price is None:
            self.pass_price = self.fee_amount
        if not self.has_pass:
            self.pass_price = None
        return self


class RSVPRequest(BaseModel):
    status: RSVPStatus


class EventPassBookingRequest(BaseModel):
    member_count: int = Field(default=1, ge=1, le=50)
    payment_method: Literal["wallet", "upi"] = "wallet"
    pin: str | None = None


class EventPassShareRequest(BaseModel):
    recipient_mobile: str = Field(min_length=7, max_length=20)
    count: int = Field(default=1, ge=1)

    @field_validator("recipient_mobile")
    @classmethod
    def validate_recipient_mobile(cls, value: str) -> str:
        if not is_phone_number(value):
            raise ValueError("Enter a valid mobile number with 7 to 15 digits.")
        return value.strip()


class EventPassScanRequest(BaseModel):
    query: str = Field(min_length=1)


class EventPassCheckInRequest(BaseModel):
    admit_count: int = Field(default=1, ge=1)
    notes: str | None = None


class EventCommentRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)

    @field_validator("comment")
    @classmethod
    def trim_comment(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment cannot be blank")
        return value


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    description: str | None = None
    category: str | None = None
    banner_url: str | None = None
    location: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    is_registration_required: bool = False
    registration_deadline: datetime | None = None
    max_capacity: int | None = None
    audience: str | None = None
    is_paid: bool = False
    fee_amount: Decimal | None = None
    has_pass: bool = False
    pass_price: Decimal | None = None
    max_passes_per_user: int = 10
    my_pass: dict | None = None
    organizer_name: str | None = None
    organizer_contact: str | None = None
    status: str | None = None
    association_id: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author_name: str | None = None
    rsvp_counts: dict[str, int] = {}
    my_rsvp_status: str | None = None
    attendees_preview: list[str] = []
    like_count: int = 0
    comment_count: int = 0
    user_has_liked: bool = False


class EventMutationResponse(BaseModel):
    updated: bool = True


class EventCreateResponse(BaseModel):
    id: str


class EventRSVPResponse(BaseModel):
    status: str | None = None


class EventLikeResponse(BaseModel):
    liked: bool


class EventCommentResponse(BaseModel):
    id: str
    event_id: str | None = None
    account_id: str | None = None
    author_name: str | None = None
    comment: str
    created_at: datetime | None = None


class EventCommentCreateResponse(BaseModel):
    id: str


EventListResponse = ApiResponse[list[EventResponse]]
EventCommentListResponse = ApiResponse[list[EventCommentResponse]]
