"""Stable amenity workflow values and role scopes."""

from enum import StrEnum

from app.core.constants import RoleCode


class AmenityPaymentMethod(StrEnum):
    WALLET = "wallet"
    UPI = "upi"


AMENITY_MANAGER_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN})
AMENITY_BOOKING_REPORT_ROLES = frozenset(
    {RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.BOARD_MEMBER}
)

