"""Account-scoped queries over shared notification content and inbox state."""

import base64
import binascii
import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        account_id: str,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        """Return one account's inbox page, its next cursor, and unread total."""
        cursor_values = _decode_cursor(cursor) if cursor else None
        query = (
            "SELECT n.id, n.title, n.message, n.type, n.entity_type, n.entity_id, "
            "n.action_url, n.metadata, r.read_at, n.created_at "
            "FROM notification_recipients r "
            "JOIN notifications n ON n.id = r.notification_id "
            "WHERE r.account_id = :account_id AND r.archived_at IS NULL"
        )
        params: dict[str, Any] = {"account_id": account_id, "limit": limit + 1}
        if cursor_values:
            query += (
                " AND (n.created_at < :cursor_created_at "
                "OR (n.created_at = :cursor_created_at AND n.id < :cursor_id))"
            )
            params.update(cursor_values)
        query += " ORDER BY n.created_at DESC, n.id DESC LIMIT :limit"
        result = await self.session.execute(text(query), params)
        rows = [_serialize_row(dict(row)) for row in result.mappings().all()]
        page = rows[:limit]
        next_cursor = _encode_cursor(page[-1]) if len(rows) > limit and page else None
        unread_count = await self.unread_count(account_id)
        return page, next_cursor, unread_count

    async def unread_count(self, account_id: str) -> int:
        result = await self.session.scalar(
            text(
                "SELECT COUNT(*) FROM notification_recipients "
                "WHERE account_id = :account_id AND archived_at IS NULL AND read_at IS NULL"
            ),
            {"account_id": account_id},
        )
        return int(result or 0)

    async def mark_read(self, notification_id: str, account_id: str) -> bool:
        result = await self.session.execute(
            text(
                "UPDATE notification_recipients SET read_at = CURRENT_TIMESTAMP "
                "WHERE notification_id = :notification_id AND account_id = :account_id "
                "AND archived_at IS NULL AND read_at IS NULL"
            ),
            {"notification_id": notification_id, "account_id": account_id},
        )
        return result.rowcount > 0

    async def mark_all_read(self, account_id: str) -> None:
        await self.session.execute(
            text(
                "UPDATE notification_recipients SET read_at = CURRENT_TIMESTAMP "
                "WHERE account_id = :account_id AND archived_at IS NULL AND read_at IS NULL"
            ),
            {"account_id": account_id},
        )


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    if isinstance(metadata, str):
        try:
            row["metadata"] = json.loads(metadata)
        except json.JSONDecodeError:
            row["metadata"] = None
    row["is_read"] = row.get("read_at") is not None
    return row


def _encode_cursor(row: dict[str, Any]) -> str:
    created_at = row["created_at"]
    payload = {"created_at": created_at.isoformat(), "id": row["id"]}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        padded_cursor = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_cursor).decode())
        created_at = datetime.fromisoformat(payload["created_at"])
        notification_id = str(payload["id"])
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError("Invalid notification cursor") from exc
    return {"cursor_created_at": created_at, "cursor_id": notification_id}
