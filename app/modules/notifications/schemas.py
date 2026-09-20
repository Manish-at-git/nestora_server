"""Notification response contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str | None = None
    is_read: bool = False
    read_at: datetime | None = None
    type: str = "system"
    entity_type: str | None = None
    entity_id: str | None = None
    action_url: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    next_cursor: str | None = None
    unread_count: int = 0


class NotificationMutationResponse(BaseModel):
    updated: bool = True
