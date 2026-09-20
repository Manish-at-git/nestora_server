from enum import StrEnum


class VendorMessage(StrEnum):
    NAME_EXISTS = "Vendor name already exists"
    NOT_FOUND = "Vendor not found"

