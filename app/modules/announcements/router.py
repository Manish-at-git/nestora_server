"""HTTP routes for announcements, reactions, and comments."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.announcements.messages import AnnouncementMessage
from app.modules.announcements.schemas import (
    AnnouncementCommentCreateResponse,
    AnnouncementCommentListResponse,
    AnnouncementCommentRequest,
    AnnouncementCommentResponse,
    AnnouncementCreateRequest,
    AnnouncementCreateResponse,
    AnnouncementLikeResponse,
    AnnouncementListResponse,
    AnnouncementMutationResponse,
    AnnouncementResponse,
)
from app.modules.announcements.service import AnnouncementService
from app.modules.notifications.service import publish_pending_notifications


router = APIRouter(tags=["Announcements"])


@router.get("/announcements", response_model=AnnouncementListResponse)
async def list_announcements(
    association_id: str | None = None,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await AnnouncementService(session).list(context.account, association_id)
    return success_response([AnnouncementResponse(**row) for row in rows])


@router.post(
    "/announcements",
    response_model=ApiResponse[AnnouncementCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_announcement(
    payload: AnnouncementCreateRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        announcement_id = await AnnouncementService(session).create(payload, context.account)
    await publish_pending_notifications(session)
    return success_response(AnnouncementCreateResponse(id=announcement_id), AnnouncementMessage.CREATED)


@router.put("/admin/announcements/{announcement_id}", response_model=ApiResponse[AnnouncementMutationResponse])
async def update_announcement(
    announcement_id: str,
    payload: AnnouncementCreateRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await AnnouncementService(session).update(announcement_id, payload, context.account)
    return success_response(AnnouncementMutationResponse(), AnnouncementMessage.UPDATED)


@router.delete("/admin/announcements/{announcement_id}", response_model=ApiResponse[AnnouncementMutationResponse])
async def delete_announcement(
    announcement_id: str,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await AnnouncementService(session).delete(announcement_id, context.account)
    return success_response(AnnouncementMutationResponse(), AnnouncementMessage.DELETED)


@router.post("/announcements/{announcement_id}/like", response_model=ApiResponse[AnnouncementLikeResponse])
async def toggle_announcement_like(
    announcement_id: str,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        liked = await AnnouncementService(session).toggle_like(announcement_id, context.account)
    return success_response(AnnouncementLikeResponse(liked=liked), AnnouncementMessage.LIKE_UPDATED)


@router.post(
    "/announcements/{announcement_id}/comment",
    response_model=ApiResponse[AnnouncementCommentCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_announcement_comment(
    announcement_id: str,
    payload: AnnouncementCommentRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        comment_id = await AnnouncementService(session).add_comment(
            announcement_id, payload, context.account
        )
    return success_response(
        AnnouncementCommentCreateResponse(id=comment_id), AnnouncementMessage.COMMENT_ADDED
    )


@router.get(
    "/announcements/{announcement_id}/comments",
    response_model=AnnouncementCommentListResponse,
)
async def list_announcement_comments(
    announcement_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await AnnouncementService(session).comments(announcement_id, context.account)
    return success_response([AnnouncementCommentResponse(**row) for row in rows])
