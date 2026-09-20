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


class AccountStatus(StrEnum):
    """Permitted account states used by authentication and future account administration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


# Keep protocol-level values in one place instead of spelling them differently
# across routers and dependencies.
CSRF_HEADER_NAME = "X-CSRF-Token"
