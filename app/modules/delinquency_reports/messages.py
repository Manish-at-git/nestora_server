from enum import StrEnum


class DelinquencyReportMessage(StrEnum):
    NOT_FOUND = "Delinquency Report not found"
    ASSOCIATION_NOT_FOUND = "Association not found"
    UNAUTHORIZED_ASSOCIATION = "You do not have access to this association"
    DUPLICATE_PERIOD = "A Delinquency Report already exists for this fiscal period"
