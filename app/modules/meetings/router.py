"""HTTP routes for meeting scheduling, attendance, and minutes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.modules.notifications.service import publish_pending_notifications
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.meetings.schemas import (
    MeetingAttendanceRequest,
    MeetingCreateRequest,
    MeetingDetailsRequest,
    MeetingMinutesRequest,
    MeetingMutationResponse,
    MeetingResponse,
)
from app.modules.meetings.service import MeetingService


router = APIRouter(tags=["Meetings"])


@router.post("/meetings", response_model=ApiResponse[MeetingMutationResponse], status_code=status.HTTP_201_CREATED)
async def create_meeting(
    payload: MeetingCreateRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await MeetingService(session).create(payload, context.account)
    await publish_pending_notifications(session)
    return success_response(MeetingMutationResponse())


@router.get("/meetings", response_model=ApiResponse[list[MeetingResponse]])
async def list_meetings(
    association_id: str | None = None,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await MeetingService(session).list(context.account, association_id)
    return success_response([MeetingResponse(**row) for row in rows])


@router.post("/meetings/{meeting_id}/attendance", response_model=ApiResponse[MeetingMutationResponse])
async def update_meeting_attendance(
    meeting_id: str,
    payload: MeetingAttendanceRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await MeetingService(session).update_attendance(meeting_id, payload, context.account)
    return success_response(MeetingMutationResponse())


@router.patch("/meetings/{meeting_id}/details", response_model=ApiResponse[MeetingMutationResponse])
async def update_meeting_details(
    meeting_id: str,
    payload: MeetingDetailsRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await MeetingService(session).update_details(meeting_id, payload, context.account)
    return success_response(MeetingMutationResponse())


@router.patch("/meetings/{meeting_id}/minutes", response_model=ApiResponse[MeetingMutationResponse])
async def add_meeting_minutes(
    meeting_id: str,
    payload: MeetingMinutesRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await MeetingService(session).add_minutes(meeting_id, payload, context.account)
    return success_response(MeetingMutationResponse())


@router.delete("/meetings/{meeting_id}", response_model=ApiResponse[MeetingMutationResponse])
async def delete_meeting(
    meeting_id: str,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await MeetingService(session).delete(meeting_id, context.account)
    return success_response(MeetingMutationResponse())
