"""Stable announcement values and authorization scopes."""

from enum import StrEnum

from app.core.constants import RoleCode


class AnnouncementCategory(StrEnum):
    GENERAL = "general"
    MAINTENANCE = "maintenance"
    URGENT = "urgent"
    CELEBRATION = "celebration"


class AnnouncementAudience(StrEnum):
    ALL = "All"
    HOMEOWNERS = "Homeowners"
    HOMEOWNER = "Homeowner"
    BOARD_MEMBER = "Board Member"
    BOARD_MEMBERS = "Board Members"
    COMMITTEE_MEMBERS = "Committee Members"
    COMMITTEE_MEMBER = "Committee Member"


ANNOUNCEMENT_MANAGER_ROLES = frozenset(
    {RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.BOARD_MEMBER}
)
