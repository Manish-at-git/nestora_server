"""Feature-specific messages for role management."""

from enum import StrEnum


class RoleMessage(StrEnum):
    """Stable messages for role validation and lifecycle operations."""

    NAME_EXISTS = "Role name already exists"
    CODE_EXISTS = "Role code already exists"
    CODE_REQUIRED = "Role code is required"
    CODE_INVALID = "Code can only contain letters, numbers, underscores (_), and hyphens (-)"
    NOT_FOUND = "Role not found"
    ASSIGNED_TO_ACCOUNT = "Cannot delete Role because it is assigned to an account"
