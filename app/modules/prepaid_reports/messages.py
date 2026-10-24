from enum import StrEnum


class PrepaidReportMessage(StrEnum):
    ASSOCIATION_NOT_FOUND = "Association not found"
    UNAUTHORIZED_ASSOCIATION = "You do not have access to this association"
    NOT_FOUND = "Prepaid Report not found"
    DUPLICATE_PERIOD = "A Prepaid Report already exists for this association and fiscal period"
