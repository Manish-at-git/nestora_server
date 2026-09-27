"""Validated request and response contracts for Email Template Master."""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class EmailTemplateRequest(BaseModel):
    """Fields accepted when creating or updating an email template."""

    name: str = Field(min_length=1, max_length=150)
    event_type: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=65535)
    is_active: bool = True

    @field_validator("name", "subject", "body")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field is required")
        return normalized

    @field_validator("event_type")
    @classmethod
    def normalize_event_type(cls, value: str) -> str:
        normalized = re.sub(r"\s+", "_", value.strip().lower())
        if not EVENT_TYPE_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Event type must start with a letter and contain only lowercase "
                "letters, numbers, and underscores"
            )
        return normalized


class EmailTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    event_type: str
    subject: str
    body: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EmailTemplateTestRequest(BaseModel):
    test_email: EmailStr
    sample_context: dict[str, Any] | None = None


class EmailTemplateTestResponse(BaseModel):
    ok: bool = True
    provider: str | None = None


class EmailTemplateMutationResponse(BaseModel):
    ok: bool = True
