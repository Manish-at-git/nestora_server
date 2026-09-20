"""Stable messages for system user administration."""

from enum import StrEnum


class UserMessage(StrEnum):
    EMAIL_EXISTS = "Email already exists"
    ROLE_NOT_FOUND = "Role not found"
    ASSOCIATION_NOT_FOUND = "Association not found"
    NOT_FOUND = "User not found"
    CODE_NOT_FOUND = "User does not have an activation code"
    EMAIL_REQUIRED = "User does not have an email"
    BLOCK_NOT_FOUND = "Block not found in the selected association"
    UNIT_NOT_FOUND = "Unit not found in the selected block"
