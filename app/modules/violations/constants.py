"""Stable violations workflow values and permitted roles."""

from enum import StrEnum

from app.core.constants import RoleCode


class ViolationStatus(StrEnum):
    NEW = "New"
    PENDING_BOARD = "Pending Board"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    DISMISSED = "Dismissed"


class ViolationAction(StrEnum):
    NONE = "None"
    FINE = "Fine"
    WAIVE_OFF = "Waive Off"


class ViolatorResponse(StrEnum):
    ACCEPT = "Accept"
    DISCUSS_WITH_BOARD = "Discuss with Board"
    EXTENSION = "Extension"


ADMIN_ROLE_CODES = frozenset({RoleCode.ADMIN, RoleCode.SUPER_ADMIN})
BOARD_ROLE_CODES = frozenset({RoleCode.BOARD_MEMBER})
# Board and Committee members remain residents of their assigned unit.  They
# can therefore be selected as a reported resident and receive resident dues.
RESIDENT_ROLE_CODES = frozenset(
    {
        RoleCode.HOMEOWNER,
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
    }
)
REPORTER_ROLE_CODES = RESIDENT_ROLE_CODES
EXCLUDED_TARGET_ROLE_CODES = frozenset(
    {
        RoleCode.ADMIN,
        RoleCode.SUPER_ADMIN,
        RoleCode.SECURITY,
        RoleCode.CSR,
        RoleCode.ACCOUNTANT,
    }
)
