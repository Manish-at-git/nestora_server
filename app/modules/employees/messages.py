"""Stable messages for employee administration."""

from enum import StrEnum


class EmployeeMessage(StrEnum):
    EMAIL_EXISTS = "Email already exists"
    ROLE_NOT_FOUND = "Role not found"
    ASSOCIATION_NOT_FOUND = "Association not found"
    NOT_FOUND = "Employee not found"
