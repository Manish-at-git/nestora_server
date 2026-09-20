"""Validated request and response contracts for role CRUD."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoleRequest(BaseModel):
    """Fields accepted when creating or updating a role."""

    entity_id: str | None = Field(default=None, max_length=36)
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=65535)
    is_active: bool = True

    @field_validator("entity_id", "name", "code", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        """Trim optional and required text before service validation."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str | None) -> str:
        """Reject blank role names."""
        if not value:
            raise ValueError("Role name is required")
        return value

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str:
        """Normalize role codes and enforce the legacy-safe character set."""
        if not value:
            raise ValueError("Role code is required")
        normalized = value.lower()
        if not re.fullmatch(r"[a-z0-9_-]+", normalized):
            raise ValueError(
                "Code can only contain letters, numbers, underscores (_), and hyphens (-)"
            )
        return normalized


class RoleResponse(BaseModel):
    """Role data returned to the administrative client."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str | None = None
    name: str
    code: str
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None
    entity_name: str | None = None


class RoleMutationResponse(BaseModel):
    """Compatibility result for update and soft-delete operations."""

    ok: bool = True
