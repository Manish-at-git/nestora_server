"""Stable messages for bank account operations."""

from enum import StrEnum


class BankMessage(StrEnum):
    NOT_FOUND = "Bank account not found"
    ASSOCIATION_NOT_FOUND = "Association not found"
    UNAUTHORIZED_ASSOCIATION = "Unauthorized for this association"
    UNAUTHORIZED_ACCOUNT = "Unauthorized to modify this bank account"
