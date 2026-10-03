"""Stable visitor-management role, status, and entry-type values."""

from enum import StrEnum

from app.core.constants import FeatureRoute, RoleCode

RESIDENT_VISITOR_ROLES = (
    RoleCode.HOMEOWNER,
    RoleCode.TENANT,
    RoleCode.BOARD_MEMBER,
    RoleCode.COMMITTEE_MEMBER,
)

SECURITY_VISITOR_ROLES = (RoleCode.SECURITY,)

VISITOR_APPROVAL_ACTION_URL = f"{FeatureRoute.PRE_APPROVED_VISITORS}?tab=approvals"

VISITOR_ADMIN_ROLES = (RoleCode.ADMIN, RoleCode.SUPER_ADMIN)


class VisitorPassStatus(StrEnum):
    ACTIVE = "Active"
    USED = "Used"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"


class VisitorVisitStatus(StrEnum):
    PENDING = "Pending"
    APPROVED = "Approved"
    DENIED = "Denied"
    CHECKED_IN = "Checked-In"
    CHECKED_OUT = "Checked-Out"


class VisitorEntryType(StrEnum):
    PRE_APPROVED = "Pre-Approved"
    WALK_IN = "Walk-In"
