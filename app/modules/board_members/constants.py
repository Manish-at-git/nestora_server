from app.core.constants import RoleCode

BOARD_MEMBER_MANAGER_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN})
BOARD_MEMBER_DIRECTORY_ROLES = frozenset({
    RoleCode.SUPER_ADMIN,
    RoleCode.ADMIN,
    RoleCode.BOARD_MEMBER,
    RoleCode.HOMEOWNER,
    RoleCode.TENANT,
    RoleCode.COMMITTEE_MEMBER,
})
