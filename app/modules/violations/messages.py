"""User-safe violations workflow messages."""


class ViolationMessage:
    FORBIDDEN = "You do not have permission to access this violation."
    NOT_FOUND = "Violation not found."
    NOT_MAPPED = "Your account is not assigned to an association unit."
    INVALID_TARGET = "Select an eligible resident in another unit of your association."
    INVALID_STATUS = "This violation cannot be updated at its current stage."
    SELF_DECISION_FORBIDDEN = "A board member cannot decide a violation reported against them."
    FINE_SETUP_REQUIRED = "Set a violation fine in Association Settings or enter an amount during review."
    RESPONSE_ALREADY_RECORDED = "A response has already been recorded for this violation."
