"""User-facing announcement API messages."""


class AnnouncementMessage:
    CREATED = "Announcement published successfully"
    UPDATED = "Announcement updated successfully"
    DELETED = "Announcement deleted successfully"
    LIKE_UPDATED = "Announcement reaction updated"
    COMMENT_ADDED = "Comment added successfully"
    FORBIDDEN = "You are not allowed to access this announcement"
    NOT_FOUND = "Announcement not found"
    BOARD_WINDOW_EXPIRED = "Board members cannot change announcements after 2 hours"
    INVALID_ASSOCIATION = "Association is invalid"

