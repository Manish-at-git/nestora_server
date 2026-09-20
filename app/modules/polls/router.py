"""HTTP routes for poll publishing, voting, likes, and comments."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.polls.messages import PollMessage
from app.modules.polls.schemas import (
    PollCommentCreateResponse, PollCommentListResponse, PollCommentRequest, PollCommentResponse,
    PollCreateRequest, PollCreateResponse, PollLikeResponse, PollListResponse, PollMutationResponse,
    PollResponse, PollVoteRequest,
)
from app.modules.polls.service import PollService
from app.modules.notifications.service import publish_pending_notifications

router = APIRouter(tags=["Polls"])


@router.get("/polls", response_model=PollListResponse)
async def list_polls(association_id: str | None = None, scope: str = "all", context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await PollService(session).list(context.account, association_id, scope)
    return success_response([PollResponse(**row) for row in rows])


@router.post("/polls", response_model=ApiResponse[PollCreateResponse], status_code=status.HTTP_201_CREATED)
async def create_poll(payload: PollCreateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        poll_id = await PollService(session).create(payload, context.account)
    await publish_pending_notifications(session)
    return success_response(PollCreateResponse(id=poll_id), PollMessage.CREATED)


@router.post("/admin/polls", response_model=ApiResponse[PollCreateResponse], status_code=status.HTTP_201_CREATED)
async def create_poll_admin_alias(payload: PollCreateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        poll_id = await PollService(session).create(payload, context.account)
    await publish_pending_notifications(session)
    return success_response(PollCreateResponse(id=poll_id), PollMessage.CREATED)


@router.put("/polls/{poll_id}", response_model=ApiResponse[PollMutationResponse])
async def update_poll(poll_id: str, payload: PollCreateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await PollService(session).update(poll_id, payload, context.account)
    await publish_pending_notifications(session)
    return success_response(PollMutationResponse(), PollMessage.UPDATED)


@router.put("/admin/polls/{poll_id}", response_model=ApiResponse[PollMutationResponse])
async def update_poll_admin_alias(poll_id: str, payload: PollCreateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await PollService(session).update(poll_id, payload, context.account)
    await publish_pending_notifications(session)
    return success_response(PollMutationResponse(), PollMessage.UPDATED)


@router.delete("/polls/{poll_id}", response_model=ApiResponse[PollMutationResponse])
async def delete_poll(poll_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await PollService(session).delete(poll_id, context.account)
    return success_response(PollMutationResponse(), PollMessage.DELETED)


@router.delete("/admin/polls/{poll_id}", response_model=ApiResponse[PollMutationResponse])
async def delete_poll_admin_alias(poll_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await PollService(session).delete(poll_id, context.account)
    return success_response(PollMutationResponse(), PollMessage.DELETED)


@router.post("/polls/{poll_id}/vote", response_model=ApiResponse[PollMutationResponse])
async def vote_poll(poll_id: str, payload: PollVoteRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await PollService(session).vote(poll_id, payload, context.account)
    return success_response(PollMutationResponse(), PollMessage.VOTED)


@router.post("/polls/{poll_id}/like", response_model=ApiResponse[PollLikeResponse])
async def toggle_like(poll_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        liked = await PollService(session).like(poll_id, context.account)
    return success_response(PollLikeResponse(liked=liked), PollMessage.LIKE_UPDATED)


@router.get("/polls/{poll_id}/comments", response_model=PollCommentListResponse)
async def list_comments(poll_id: str, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await PollService(session).comments(poll_id, context.account)
    return success_response([PollCommentResponse(**row) for row in rows])


@router.post("/polls/{poll_id}/comments", response_model=ApiResponse[PollCommentCreateResponse], status_code=status.HTTP_201_CREATED)
async def add_comment(poll_id: str, payload: PollCommentRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        comment_id = await PollService(session).add_comment(poll_id, payload, context.account)
    return success_response(PollCommentCreateResponse(id=comment_id), PollMessage.COMMENT_ADDED)
