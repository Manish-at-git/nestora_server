"""Validated request and response contracts for entity type CRUD."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntityTypeRequest(BaseModel):
    """Fields accepted when creating or updating an entity type."""

    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=65535)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Reject blank names while keeping stored values readable."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name is required")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        """Store empty descriptions as NULL rather than meaningless whitespace."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class EntityTypeResponse(BaseModel):
    """Safe entity type data returned to the administrative client."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    created_at: datetime | None = None


class EntityTypeMutationResponse(BaseModel):
    """Compatibility result for update and delete operations."""

    ok: bool = True
