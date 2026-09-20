"""Validated service-request request and response contracts."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.service_requests.constants import ServiceRequestStatus


class ServiceRequestCreateRequest(BaseModel):
    service_type: str = Field(min_length=1, max_length=100)
    sub_category: str | None = Field(default=None, max_length=100)
    custom_title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    image_url: str | None = Field(default=None, max_length=255)
    user_id: str | None = Field(default=None, max_length=36)
    incoming_call_no: str | None = Field(default=None, max_length=30)
    association_id: str | None = Field(default=None, max_length=36)

    @field_validator(
        "service_type",
        "sub_category",
        "custom_title",
        "description",
        "image_url",
        "user_id",
        "incoming_call_no",
        "association_id",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class ServiceRequestStatusRequest(BaseModel):
    status: ServiceRequestStatus

    @field_validator("status", mode="before")
    @classmethod
    def normalize_legacy_status(cls, value: str) -> str:
        aliases = {
            "pending": ServiceRequestStatus.NEW,
            "new": ServiceRequestStatus.NEW,
            "in progress": ServiceRequestStatus.IN_PROGRESS,
            "complete": ServiceRequestStatus.COMPLETE,
            "completed": ServiceRequestStatus.COMPLETE,
            "cancel": ServiceRequestStatus.CANCEL,
            "cancelled": ServiceRequestStatus.CANCEL,
            "canceled": ServiceRequestStatus.CANCEL,
        }
        return aliases.get(str(value).strip().lower(), value)


class ServiceRequestMappingRequest(BaseModel):
    association_id: str = Field(min_length=1, max_length=36)
    unit_id: str = Field(min_length=1, max_length=36)
    user_id: str = Field(min_length=1, max_length=36)


class ServiceRequestMessageRequest(BaseModel):
    message: str | None = Field(default=None, max_length=5000)
    attachment_url: str | None = Field(default=None, max_length=255)

    @field_validator("message", "attachment_url", mode="before")
    @classmethod
    def empty_strings_are_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def require_content(self) -> "ServiceRequestMessageRequest":
        if not self.message and not self.attachment_url:
            raise ValueError("A message or attachment is required")
        return self


class ServiceRequestResponse(BaseModel):
    id: str
    sr_display_id: str | None = None
    service_type: str
    sub_category: str | None = None
    custom_title: str | None = None
    description: str | None = None
    image_url: str | None = None
    status: str
    incoming_call_no: str | None = None
    user_id: str | None = None
    association_id: str | None = None
    unit_id: str | None = None
    unit_number: str | None = None
    block_name: str | None = None
    association_name: str | None = None
    requestor_name: str | None = None
    requestor_phone: str | None = None
    requestor_email: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ServiceRequestMessageResponse(BaseModel):
    id: str
    service_request_id: str
    sender_id: str
    message: str | None = None
    attachment_url: str | None = None
    created_at: datetime
    email: str | None = None
    role_id: str | None = None
    sender_name: str | None = None


class ServiceRequestCreateResponse(BaseModel):
    id: str


class ServiceRequestMutationResponse(BaseModel):
    updated: bool = True


class ServiceRequestMessageCreateResponse(BaseModel):
    id: str


class BlockResponse(BaseModel):
    id: str
    name: str


class UnitResponse(BaseModel):
    id: str
    unit_number: str
    block_name: str | None = None


class ResidentResponse(BaseModel):
    user_id: str
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
