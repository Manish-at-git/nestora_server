"""Stable meeting values and role scopes."""

from enum import StrEnum

from app.core.constants import RoleCode


class MeetingStatus(StrEnum):
    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"


class MeetingAudience(StrEnum):
    BOARD_MEMBERS = "Board Members"
    COMMITTEE_MEMBER = "Committee Member"
    HOMEOWNER = "Homeowner"


MEETING_ADMIN_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT})
MEETING_EDITOR_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN})
MEETING_CREATOR_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.BOARD_MEMBER})
MEETING_RSVP_ROLES = frozenset(
    {
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
        RoleCode.HOMEOWNER,
        RoleCode.TENANT,
    }
)
AUDIENCE_ROLE_CODES = {
    MeetingAudience.BOARD_MEMBERS: RoleCode.BOARD_MEMBER,
    MeetingAudience.COMMITTEE_MEMBER: RoleCode.COMMITTEE_MEMBER,
    MeetingAudience.HOMEOWNER: RoleCode.HOMEOWNER,
}
