"""User-facing service-request messages."""


class ServiceRequestMessage:
    NOT_FOUND = "Service request not found"
    FORBIDDEN = "You do not have access to this service request"
    USER_NOT_MAPPED = "User is not mapped to an association"
    INVALID_ASSOCIATION = "The selected resident does not belong to this association"
    INVALID_UNIT = "The selected unit does not belong to this association"
    INVALID_RESIDENT = "The selected resident does not belong to this unit"
    CREATED = "Service request created"
    UPDATED = "Service request status updated"
    MAPPED = "Service request mapped successfully"
    DELETED = "Service request deleted"
    MESSAGE_SENT = "Message sent"
