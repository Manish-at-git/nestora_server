"""Feature-specific messages for entity type management."""

from enum import StrEnum


class EntityTypeMessage(StrEnum):
    """Stable messages for duplicate and missing entity type operations."""

    NAME_EXISTS = "Entity type name already exists"
    NOT_FOUND = "Entity type not found"
