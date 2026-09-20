"""Stable service-request workflow values and role groups."""

from enum import StrEnum

from app.core.constants import RoleCode


class ServiceRequestStatus(StrEnum):
    NEW = "New"
    IN_PROGRESS = "In Progress"
    COMPLETE = "Complete"
    CANCEL = "Cancel"


ADMIN_ROLE_CODES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN})
ASSOCIATION_VIEW_ROLE_CODES = frozenset(
    {
        RoleCode.SUPER_ADMIN,
        RoleCode.ADMIN,
        RoleCode.SECURITY,
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
    }
)
STATUS_MANAGER_ROLE_CODES = frozenset(
    {
        RoleCode.SUPER_ADMIN,
        RoleCode.ADMIN,
        RoleCode.SECURITY,
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
    }
)
