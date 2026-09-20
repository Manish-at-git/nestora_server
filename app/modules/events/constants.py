"""Stable event values and role-code scopes."""

from enum import StrEnum

from app.core.constants import RoleCode


class RSVPStatus(StrEnum):
    GOING = "going"
    MAYBE = "maybe"
    NOT_GOING = "not_going"


class EventAudience(StrEnum):
    ALL = "All"
    HOMEOWNER = "Homeowner"
    HOMEOWNERS = "Homeowners"
    BOARD_MEMBER = "Board Member"
    BOARD_MEMBERS = "Board Members"
    COMMITTEE_MEMBER = "Committee Member"
    COMMITTEE_MEMBERS = "Committee Members"


EVENT_MANAGER_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.BOARD_MEMBER})
EVENT_RSVP_ROLES = frozenset({RoleCode.HOMEOWNER, RoleCode.TENANT, RoleCode.BOARD_MEMBER, RoleCode.COMMITTEE_MEMBER, RoleCode.ADMIN, RoleCode.SUPER_ADMIN})
