"""Validated request and response contracts for feature CRUD."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FeatureRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=65535)
    parent_id: str | None = Field(default=None, max_length=36)
    icon: str | None = Field(default=None, max_length=65535)
    url: str | None = Field(default=None, max_length=255)
    is_active: bool = True

    @field_validator("name", "code", "description", "parent_id", "icon", "url")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str | None) -> str:
        if not value:
            raise ValueError("Feature name is required")
        return value

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str:
        if not value:
            raise ValueError("Feature code is required")
        value = value.lower()
        if not re.fullmatch(r"[a-z0-9_-]+", value):
            raise ValueError("Code can only contain letters, numbers, underscores (_), and hyphens (-)")
        return value


class FeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    code: str | None = None
    description: str | None = None
    parent_id: str | None = None
    parent_name: str | None = None
    icon: str | None = None
    url: str | None = None
    order_index: int = 0
    is_active: bool
    created_at: datetime | None = None


class FeatureMutationResponse(BaseModel):
    ok: bool = True
