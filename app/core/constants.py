"""Application-wide stable constants shared by every module.

Keep machine-readable values here when they are stored in the database,
checked by authorization, or exchanged with the client.  Display text belongs
in the relevant module or database record, because it can change independently.
"""

from enum import StrEnum


class RoleCode(StrEnum):
    """Stable database values for every currently known Nestora role."""

    COMMITTEE_MEMBER = "committee_member"
    HOMEOWNER = "homeowner"
    SECURITY = "security"
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    TENANT = "tenant"
    BOARD_MEMBER = "board_member"
    ACCOUNTANT = "accountant"
    CSR = "csr"


class FeatureCode(StrEnum):
    """Stable feature identifiers shared by authorization and navigation contracts."""

    EMAIL_TEMPLATES = "email_templates"
    NEARBY_PLACES = "nearby_places"
    CHAT_POOL = "chat_pool"
    VISITOR_MANAGEMENT = "visitor_management"
    # Retained only to hide the superseded feature during permission seeding.
    LEGACY_VISITOR_PASSES = "visitor_passes"
    LEGACY_NEW_VISITOR = "new_visitor"
    LEGACY_CHECK_IN = "check_in"
    LEGACY_CHECK_OUT = "check_out"
    LEGACY_ACTIVE_VISITORS = "active_visitors"
    GATE_CONSOLE = "gate_console"
    PRE_APPROVED_VISITORS = "pre_approved_visitors"
    VISITOR_HISTORY = "visitor_history"


class FeatureName(StrEnum):
    """Stable display names used when a feature must be created by a seed."""

    EMAIL_TEMPLATES = "Email Templates"
    NEARBY_PLACES = "Nearby Places"
    CHAT_POOL = "Chat Pool"
    VISITOR_MANAGEMENT = "Visitor Management"
    GATE_CONSOLE = "New Visitor"
    PRE_APPROVED_VISITORS = "Pre-Approved Visitors"
    VISITOR_HISTORY = "Visitor History"


class FeatureRoute(StrEnum):
    """Stable client routes used by seeded feature catalogue records."""

    EMAIL_TEMPLATES = "/email-templates"
    NEARBY_PLACES = "/nearby-places"
    CHAT_POOL = "/chat"
    VISITOR_MANAGEMENT = "/visitor-management"
    GATE_CONSOLE = "/visitor-management/new"
    PRE_APPROVED_VISITORS = "/visitor-management/preapproved"
    VISITOR_HISTORY = "/visitor-management/history"


class AccountStatus(StrEnum):
    """Permitted account states used by authentication and future account administration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


# Keep protocol-level values in one place instead of spelling them differently
# across routers and dependencies.
CSRF_HEADER_NAME = "X-CSRF-Token"
