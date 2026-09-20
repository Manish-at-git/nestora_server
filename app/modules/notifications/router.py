"""Authenticated notification inbox endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import (
    NotificationListResponse,
    NotificationMutationResponse,
    NotificationResponse,
)


router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=ApiResponse[NotificationListResponse])
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        rows, next_cursor, unread_count = await NotificationRepository(session).list(
            context.account.id,
            limit,
            cursor,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid notification cursor") from exc
    return success_response(
        NotificationListResponse(
            items=[NotificationResponse(**row) for row in rows],
            next_cursor=next_cursor,
            unread_count=unread_count,
        )
    )


@router.patch("/{notification_id}/read", response_model=ApiResponse[NotificationMutationResponse])
async def mark_notification_read(
    notification_id: str,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        updated = await NotificationRepository(session).mark_read(
            notification_id,
            context.account.id,
        )
        if not updated:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    return success_response(NotificationMutationResponse(), "Notification marked as read")


@router.post("/read-all", response_model=ApiResponse[NotificationMutationResponse])
async def mark_all_notifications_read(
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await NotificationRepository(session).mark_all_read(context.account.id)
    return success_response(NotificationMutationResponse(), "Notifications marked as read")
