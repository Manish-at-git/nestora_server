"""Stable messages for Balance Sheet operations."""

from enum import StrEnum


class BalanceSheetMessage(StrEnum):
    ASSOCIATION_NOT_FOUND = "Association not found"
    NOT_FOUND = "Balance Sheet not found"
    DUPLICATE_DATE = "A Balance Sheet already exists for this association and date"
    UNAUTHORIZED_ASSOCIATION = "You are not authorized to access this association"
    UNBALANCED = "Total assets must equal total liabilities plus equity"
    EMPTY_IMPORT = "The spreadsheet does not contain any Balance Sheet items"
