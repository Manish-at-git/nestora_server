"""Focused tests for shared notification payloads and recipient inbox state."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.modules.notifications.repository import _decode_cursor, _encode_cursor
from app.modules.notifications.service import notify_accounts


class _MappingsResult:
    def __init__(self, row: dict) -> None:
        self._row = row

    def mappings(self) -> "_MappingsResult":
        return self

    def first(self) -> dict:
        return self._row


@pytest.mark.asyncio
async def test_broadcast_creates_one_payload_and_one_recipient_row_per_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.info = {}
    session.execute.side_effect = [None, None, _MappingsResult({
        "id": "notification-1",
        "title": "New announcement",
        "message": "Community update",
        "type": "announcement",
        "entity_type": "announcement",
        "entity_id": "announcement-1",
        "action_url": "/announcements",
        "metadata": None,
        "created_at": datetime(2026, 9, 20, 10, 0),
    })]
    monkeypatch.setattr(
        "app.modules.notifications.service._existing_account_ids",
        AsyncMock(return_value=["account-1", "account-2"]),
    )

    notifications = await notify_accounts(
        session,
        ["account-1", "account-2"],
        "New announcement",
        "Community update",
        notification_type="announcement",
        entity_type="announcement",
        entity_id="announcement-1",
        action_url="/announcements",
    )

    assert len(notifications) == 2
    assert notifications[0]["id"] == notifications[1]["id"]
    assert notifications[0]["is_read"] is False

    parent_insert = session.execute.call_args_list[0]
    recipient_insert = session.execute.call_args_list[1]
    assert "INSERT INTO notifications" in str(parent_insert.args[0])
    assert "INSERT INTO notification_recipients" in str(recipient_insert.args[0])
    assert len(recipient_insert.args[1]) == 2
    assert len(session.info["notification_deliveries"]) == 2


def test_notification_cursor_round_trip() -> None:
    row = {"id": "notification-1", "created_at": datetime(2026, 9, 20, 10, 0)}

    decoded = _decode_cursor(_encode_cursor(row))

    assert decoded == {
        "cursor_created_at": datetime(2026, 9, 20, 10, 0),
        "cursor_id": "notification-1",
    }


def test_invalid_notification_cursor_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid notification cursor"):
        _decode_cursor("not-a-valid-cursor")
