"""Feature-specific Email Template Master messages."""

from enum import StrEnum


class EmailTemplateMessage(StrEnum):
    EVENT_TYPE_EXISTS = "An email template already exists for this event type"
    NOT_FOUND = "Email template not found"
    TEST_SEND_FAILED = "Test email could not be sent"
