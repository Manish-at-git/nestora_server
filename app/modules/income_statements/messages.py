from enum import StrEnum


class IncomeStatementMessage(StrEnum):
    ASSOCIATION_NOT_FOUND = "Association not found"
    NOT_FOUND = "Income Statement not found"
    DUPLICATE_PERIOD = "An Income Statement already exists for this fiscal period"
    UNAUTHORIZED_ASSOCIATION = "You are not authorized to access this association"
