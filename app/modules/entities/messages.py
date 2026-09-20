"""Feature-specific messages for entity management."""

from enum import StrEnum


class EntityMessage(StrEnum):
    """Stable messages for duplicate and missing entity operations."""

    NAME_EXISTS = "Entity name already exists for this type"
    NOT_FOUND = "Entity not found"
