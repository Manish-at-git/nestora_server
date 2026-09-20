from app.core.constants import RoleCode


WALLET_ROLE_CODES = frozenset(
    {
        RoleCode.SUPER_ADMIN,
        RoleCode.ADMIN,
        RoleCode.ACCOUNTANT,
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
        RoleCode.HOMEOWNER,
        RoleCode.TENANT,
    }
)
