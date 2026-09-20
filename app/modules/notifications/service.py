"""Persist shared notification content and account-specific inbox state."""

import json
import uuid
from collections.abc import Iterable
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AccountStatus, RoleCode


_DELIVERIES_KEY = "notification_deliveries"


async def create_notification(
    session: AsyncSession,
    account_id: str | None,
    title: str,
    message: str,
    *,
    notification_type: str = "system",
    association_id: str | None = None,
    created_by_account_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Create one notification for one account using the shared data model."""
    if not account_id:
        return None
    notifications = await notify_accounts(
        session,
        [account_id],
        title,
        message,
        notification_type=notification_type,
        association_id=association_id,
        created_by_account_id=created_by_account_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action_url=action_url,
        metadata=metadata,
    )
    return notifications[0] if notifications else None


async def notify_accounts(
    session: AsyncSession,
    account_ids: Iterable[str],
    title: str,
    message: str,
    sender_account_id: str | None = None,
    *,
    notification_type: str = "system",
    association_id: str | None = None,
    created_by_account_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Create one immutable payload and one inbox-state row per valid recipient."""
    recipient_ids = await _existing_account_ids(session, account_ids, sender_account_id)
    if not recipient_ids:
        return []

    notification_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO notifications ("
            "id, association_id, created_by_account_id, type, title, message, "
            "entity_type, entity_id, action_url, metadata"
            ") VALUES ("
            ":id, :association_id, :created_by_account_id, :type, :title, :message, "
            ":entity_type, :entity_id, :action_url, :metadata"
            ")"
        ),
        {
            "id": notification_id,
            "association_id": association_id,
            "created_by_account_id": created_by_account_id or sender_account_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action_url": action_url,
            "metadata": json.dumps(jsonable_encoder(metadata)) if metadata else None,
        },
    )
    await session.execute(
        text(
            "INSERT INTO notification_recipients (notification_id, account_id, delivered_at) "
            "VALUES (:notification_id, :account_id, CURRENT_TIMESTAMP)"
        ),
        [
            {"notification_id": notification_id, "account_id": account_id}
            for account_id in recipient_ids
        ],
    )

    result = await session.execute(
        text(
            "SELECT id, title, message, type, entity_type, entity_id, action_url, "
            "metadata, created_at FROM notifications WHERE id = :id"
        ),
        {"id": notification_id},
    )
    row = result.mappings().first()
    if row is None:
        return []

    notification = {**dict(row), "is_read": False, "read_at": None}
    deliveries = session.info.setdefault(_DELIVERIES_KEY, [])
    for account_id in recipient_ids:
        deliveries.append((account_id, notification.copy()))
    return [notification.copy() for _ in recipient_ids]


async def notify_association_audience(
    session: AsyncSession,
    association_id: str,
    audience: str,
    title: str,
    message: str,
    sender_account_id: str | None,
    target_block_id: str | None = None,
    *,
    notification_type: str = "system",
    entity_type: str | None = None,
    entity_id: str | None = None,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Notify active accounts in the selected association audience."""
    role_codes = _audience_role_codes(audience)
    if not role_codes:
        return []
    query = (
        "SELECT DISTINCT ac.account_id FROM accounts ac "
        "JOIN roles r ON r.id = ac.role_id "
        "JOIN user_details ud ON ud.user_id = ac.user_id "
        "JOIN units u ON u.id = ud.unit_id "
        "JOIN blocks b ON b.id = u.block_id "
        "WHERE ac.status = :account_status AND r.is_active = 1 AND r.is_deleted = 0 "
        "AND ud.is_deleted = 0 AND b.association_id = :association_id "
        "AND r.code IN :role_codes"
    )
    params = {
        "account_status": AccountStatus.ACTIVE,
        "association_id": association_id,
        "role_codes": tuple(role_codes),
    }
    if target_block_id:
        query += " AND b.id = :target_block_id"
        params["target_block_id"] = target_block_id
    result = await session.scalars(
        text(query).bindparams(bindparam("role_codes", expanding=True)),
        params,
    )
    return await notify_accounts(
        session,
        result.all(),
        title,
        message,
        sender_account_id,
        notification_type=notification_type,
        association_id=association_id,
        created_by_account_id=sender_account_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action_url=action_url,
        metadata=metadata,
    )


async def publish_pending_notifications(session: AsyncSession) -> None:
    """Send committed notification payloads to their intended account sockets."""
    deliveries = session.info.pop(_DELIVERIES_KEY, [])
    if not deliveries:
        return
    from app.core.realtime import manager

    for account_id, notification in deliveries:
        await manager.send_to_accounts(
            [account_id],
            {
                "type": "notification.created",
                "notification": jsonable_encoder(notification),
            },
        )


async def _existing_account_ids(
    session: AsyncSession,
    account_ids: Iterable[str],
    sender_account_id: str | None,
) -> list[str]:
    requested = tuple(
        account_id
        for account_id in dict.fromkeys(account_ids)
        if account_id and account_id != sender_account_id
    )
    if not requested:
        return []
    result = await session.scalars(
        text("SELECT account_id FROM accounts WHERE account_id IN :account_ids").bindparams(
            bindparam("account_ids", expanding=True)
        ),
        {"account_ids": requested},
    )
    return list(result.all())


def _audience_role_codes(audience: str) -> tuple[RoleCode, ...]:
    normalized = audience.strip().lower().replace("_", " ").replace("-", " ")
    if normalized in {"all", "all members"}:
        return (
            RoleCode.HOMEOWNER,
            RoleCode.TENANT,
            RoleCode.BOARD_MEMBER,
            RoleCode.COMMITTEE_MEMBER,
        )
    if normalized in {"homeowner", "homeowners"}:
        return (RoleCode.HOMEOWNER, RoleCode.TENANT)
    if normalized in {"committee member", "committee members"}:
        return (RoleCode.COMMITTEE_MEMBER,)
    if normalized in {"board member", "board members"}:
        return (RoleCode.BOARD_MEMBER,)
    return ()
