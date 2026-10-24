from enum import StrEnum


class VendorAgingReportMessage(StrEnum):
    ASSOCIATION_NOT_FOUND = "Association not found"
    UNAUTHORIZED_ASSOCIATION = "You do not have access to this association"
    NOT_FOUND = "Vendor Aging Report not found"
    DUPLICATE_PERIOD = "A Vendor Aging Report already exists for this association and fiscal period"
