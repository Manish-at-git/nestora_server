"""Validated request and response contracts for entity CRUD."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntityRequest(BaseModel):
    """Fields accepted when creating or updating an entity."""

    entity_type_id: str = Field(min_length=1, max_length=36)
    association_id: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=65535)

    @field_validator("entity_type_id", "association_id", "name", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        """Trim user-entered identifiers and text while preserving optional NULL values."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str | None) -> str:
        """Reject names made only of whitespace."""
        if not value:
            raise ValueError("Name is required")
        return value

    @field_validator("entity_type_id")
    @classmethod
    def require_entity_type(cls, value: str | None) -> str:
        """Reject a missing entity type before database work begins."""
        if not value:
            raise ValueError("Entity type is required")
        return value


class EntityResponse(BaseModel):
    """Entity data returned to the administrative client."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type_id: str | None = None
    entity_type_name: str | None = None
    association_id: str | None = None
    name: str
    description: str | None = None
    created_at: datetime | None = None


class EntityMutationResponse(BaseModel):
    """Compatibility result for update and soft-delete operations."""

    ok: bool = True
