"""HTTP routes for event publishing, RSVP, likes, and comments."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.events.messages import EventMessage
from app.modules.events.schemas import (
    EventCommentCreateResponse, EventCommentListResponse, EventCommentRequest, EventCommentResponse,
    EventCreateRequest, EventCreateResponse, EventLikeResponse, EventListResponse, EventMutationResponse,
    EventResponse, EventRSVPResponse, RSVPRequest,
)
from app.modules.events.service import EventService
from app.modules.notifications.service import publish_pending_notifications

router = APIRouter(tags=["Events"])


@router.get("/events", response_model=EventListResponse)
async def list_events(scope: str = "upcoming", association_id: str | None = None, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await EventService(session).list(context.account, scope, association_id)
    return success_response([EventResponse(**row) for row in rows])


@router.post("/events", response_model=ApiResponse[EventCreateResponse], status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventCreateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        event_id = await EventService(session).create(payload, context.account)
    await publish_pending_notifications(session)
    return success_response(EventCreateResponse(id=event_id), EventMessage.CREATED)


@router.post("/admin/events", response_model=ApiResponse[EventCreateResponse], status_code=status.HTTP_201_CREATED)
async def admin_create_event_alias(payload: EventCreateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        event_id = await EventService(session).create(payload, context.account)
    await publish_pending_notifications(session)
    return success_response(EventCreateResponse(id=event_id), EventMessage.CREATED)


@router.put("/admin/events/{event_id}", response_model=ApiResponse[EventMutationResponse])
async def update_event(event_id: str, payload: EventCreateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await EventService(session).update(event_id, payload, context.account)
    await publish_pending_notifications(session)
    return success_response(EventMutationResponse(), EventMessage.UPDATED)


@router.delete("/admin/events/{event_id}", response_model=ApiResponse[EventMutationResponse])
async def delete_event(event_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await EventService(session).delete(event_id, context.account)
    return success_response(EventMutationResponse(), EventMessage.DELETED)


@router.post("/events/{event_id}/rsvp", response_model=ApiResponse[EventRSVPResponse])
async def rsvp_event(event_id: str, payload: RSVPRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        selected = await EventService(session).rsvp(event_id, payload, context.account)
    return success_response(EventRSVPResponse(status=selected), EventMessage.RSVP_UPDATED)


@router.delete("/events/{event_id}/rsvp", response_model=ApiResponse[EventMutationResponse])
async def clear_rsvp(event_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await EventService(session).clear_rsvp(event_id, context.account)
    return success_response(EventMutationResponse(), EventMessage.RSVP_CLEARED)


@router.get("/admin/events/{event_id}/rsvps", response_model=ApiResponse[dict])
async def admin_event_rsvps(event_id: str, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    data = await EventService(session).admin_rsvps(event_id, context.account)
    return success_response(data)


@router.post("/events/{event_id}/like", response_model=ApiResponse[EventLikeResponse])
async def toggle_like(event_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        liked = await EventService(session).like(event_id, context.account)
    return success_response(EventLikeResponse(liked=liked), EventMessage.LIKE_UPDATED)


@router.get("/events/{event_id}/comments", response_model=EventCommentListResponse)
async def list_comments(event_id: str, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await EventService(session).comments(event_id, context.account)
    return success_response([EventCommentResponse(**row) for row in rows])


@router.post("/events/{event_id}/comments", response_model=ApiResponse[EventCommentCreateResponse], status_code=status.HTTP_201_CREATED)
async def add_comment(event_id: str, payload: EventCommentRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        comment_id = await EventService(session).add_comment(event_id, payload, context.account)
    return success_response(EventCommentCreateResponse(id=comment_id), EventMessage.COMMENT_ADDED)
