"""Stable API messages for board tasks."""


class BoardTaskMessage:
    CREATED = "Board task created successfully."
    UPDATED = "Board task updated successfully."
    MESSAGE_SENT = "Board task message sent successfully."
    NOT_FOUND = "Board task not found."
    FORBIDDEN = "You do not have access to this board task."
    INVALID_STATUS = "Invalid board task status."
    INVALID_ASSOCIATION = "The selected association is not available to this account."
    INVALID_SUPERVISOR = "The selected supervisor is not a board member of this association."
