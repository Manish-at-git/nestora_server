"""Reusable API messages shared by routers, services, and exception handlers.

Use these only for generic outcomes that mean the same thing everywhere.
Feature-specific wording, such as login or password-reset messages, should
live inside its module so this file does not become an unstructured dump.
"""

from enum import StrEnum


class Message(StrEnum):
    """Common response messages that are safe to expose to API callers."""

    SUCCESS = "Success"
    CREATED = "Created successfully"
    NOT_FOUND = "Not found"
    UNAUTHORIZED = "Unauthorized"
    INVALID_CREDENTIALS = "Invalid email or password"
    FORBIDDEN = "Forbidden"
    BAD_REQUEST = "Bad request"
    INTERNAL_ERROR = "Internal server error"
    VALIDATION_ERROR = "Request validation failed"
    TOO_MANY_REQUESTS = "Too many requests, please try again later"
    PASSWORD_RESET_REQUEST_ACCEPTED = "If an account matches this email, reset instructions have been sent"
    PASSWORD_RESET_TOKEN_VALID = "Password reset token is valid"
    PASSWORD_UPDATED = "Password updated successfully"
