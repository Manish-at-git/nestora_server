"""Stable board-task workflow values and role scopes."""

from enum import StrEnum

from app.core.constants import RoleCode


class BoardTaskStatus(StrEnum):
    NEW = "New"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


BOARD_TASK_MANAGER_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.BOARD_MEMBER})
BOARD_TASK_ADMIN_ROLES = frozenset({RoleCode.SUPER_ADMIN, RoleCode.ADMIN})
