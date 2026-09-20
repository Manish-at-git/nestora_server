from enum import StrEnum

from app.core.constants import RoleCode


class PollVisibility(StrEnum):
    ALL = "All"
    HOMEOWNER = "Homeowner"
    HOMEOWNERS = "Homeowners"
    BOARD_MEMBER = "Board Member"
    BOARD_MEMBERS = "Board Members"
    COMMITTEE_MEMBER = "Committee Member"
    COMMITTEE_MEMBERS = "Committee Members"


POLL_MANAGER_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.BOARD_MEMBER})
POLL_VOTER_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.BOARD_MEMBER, RoleCode.COMMITTEE_MEMBER, RoleCode.HOMEOWNER, RoleCode.TENANT})
