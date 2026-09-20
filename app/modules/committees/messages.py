"""User-facing committee API messages."""


class CommitteeMessage:
    CREATED = "Committee created successfully"
    UPDATED = "Committee updated successfully"
    DELETED = "Committee deleted successfully"
    MEMBER_ASSIGNED = "Committee member assigned successfully"
    MEMBER_UPDATED = "Committee member updated successfully"
    MEMBER_REMOVED = "Committee member removed successfully"
    FORBIDDEN = "You are not allowed to manage this committee"
    NOT_FOUND = "Committee not found"
    MEMBER_NOT_FOUND = "Committee member not found"
    INVALID_ASSOCIATION = "Association is invalid"
    INVALID_MEMBER = "The selected user must be an active homeowner in this association"
    DUPLICATE_MEMBER = "User is already a member of this committee"

