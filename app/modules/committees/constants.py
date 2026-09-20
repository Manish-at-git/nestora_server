"""Stable committee workflow values and role scopes."""

from app.core.constants import RoleCode


COMMITTEE_MANAGER_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.BOARD_MEMBER})
COMMITTEE_DIRECTORY_ROLES = frozenset(
    {
        RoleCode.SUPER_ADMIN,
        RoleCode.ADMIN,
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
        RoleCode.HOMEOWNER,
        RoleCode.TENANT,
    }
)
