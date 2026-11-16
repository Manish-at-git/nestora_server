"""HTTP wiring for violations; all mutation endpoints require CSRF."""

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.realtime import manager
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.notifications.service import publish_pending_notifications
from app.modules.violations.schemas import (
    ActiveViolationFineResponse,
    EligibleResidentResponse,
    IdResponse,
    ViolationAdminReviewRequest,
    ViolationBoardDecisionRequest,
    ViolationCreateRequest,
    ViolationFineDefaultResponse,
    ViolationMessageRequest,
    ViolationMessageResponse,
    ViolationResponse,
    ViolatorResponseRequest,
)
from app.modules.violations.service import ViolationService

router = APIRouter(prefix="/violations", tags=["Violations"])


@router.get("/eligible-residents", response_model=ApiResponse[list[EligibleResidentResponse]])
async def eligible_residents(context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response([EligibleResidentResponse(**row) for row in await ViolationService(session).eligible_residents(context.account)])


@router.get("", response_model=ApiResponse[list[ViolationResponse]])
async def list_violations(scope: str, association_id: str | None = None, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response([ViolationResponse(**row) for row in await ViolationService(session).list(scope, association_id, context.account)])


@router.post("", response_model=ApiResponse[IdResponse], status_code=status.HTTP_201_CREATED)
async def create_violation(payload: ViolationCreateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        violation_id = await ViolationService(session).create(payload, context.account)
    await publish_pending_notifications(session)
    return success_response(IdResponse(id=violation_id), "Violation submitted for review.")


@router.get("/dues", response_model=ApiResponse[list[ActiveViolationFineResponse]])
async def homeowner_active_fines(context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await ViolationService(session).homeowner_active_fines(context.account)
    return success_response([ActiveViolationFineResponse(**row) for row in rows])


@router.get("/{violation_id}", response_model=ApiResponse[ViolationResponse])
async def detail(violation_id: str, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response(ViolationResponse(**(await ViolationService(session).detail(violation_id, context.account))))


@router.get("/{violation_id}/fine-default", response_model=ApiResponse[ViolationFineDefaultResponse])
async def fine_default(violation_id: str, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response(ViolationFineDefaultResponse(**(await ViolationService(session).fine_default(violation_id, context.account))))


@router.patch("/{violation_id}/admin-review", response_model=ApiResponse[dict])
async def admin_review(violation_id: str, payload: ViolationAdminReviewRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await ViolationService(session).admin_review(violation_id, payload, context.account)
    await publish_pending_notifications(session)
    return success_response({"updated": True}, "Violation review saved.")


@router.patch("/{violation_id}/board-decision", response_model=ApiResponse[dict])
async def board_decision(violation_id: str, payload: ViolationBoardDecisionRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await ViolationService(session).board_decision(violation_id, payload, context.account)
    await publish_pending_notifications(session)
    return success_response({"updated": True}, "Board decision saved.")


@router.post("/{violation_id}/response", response_model=ApiResponse[dict])
async def respond(violation_id: str, payload: ViolatorResponseRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await ViolationService(session).respond(violation_id, payload.response.value, context.account)
    await publish_pending_notifications(session)
    return success_response({"updated": True}, "Response recorded.")


@router.get("/{violation_id}/messages", response_model=ApiResponse[list[ViolationMessageResponse]])
async def messages(violation_id: str, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response([ViolationMessageResponse(**row) for row in await ViolationService(session).messages(violation_id, context.account)])


@router.post("/{violation_id}/messages", response_model=ApiResponse[IdResponse], status_code=status.HTTP_201_CREATED)
async def send_message(violation_id: str, payload: ViolationMessageRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        event = await ViolationService(session).send_message(violation_id, payload, context.account)
    await manager.send_to_accounts(event.recipient_account_ids, {"type": "violation.message", "violation_id": violation_id, "message": jsonable_encoder(event.message)})
    await publish_pending_notifications(session)
    return success_response(IdResponse(id=event.message["id"]), "Message sent.")
