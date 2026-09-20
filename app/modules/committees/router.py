"""HTTP routes for committees, memberships, and homeowner candidates."""

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.core.realtime import manager
from app.modules.notifications.service import notify_accounts, publish_pending_notifications
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.committees.messages import CommitteeMessage
from app.modules.committees.schemas import (
    CommitteeCreateRequest,
    CommitteeMemberAssignRequest,
    CommitteeMemberResponse,
    CommitteeMemberUpdateRequest,
    CommitteeResponse,
    CommitteeUpdateRequest,
    CommitteeChatMessageRequest,
    CommitteeChatMessageResponse,
    HomeownerResponse,
    IdResponse,
    MutationResponse,
)
from app.modules.committees.service import CommitteeService


router = APIRouter(tags=["Committees"])


@router.get("/admin/committees", response_model=ApiResponse[list[CommitteeResponse]])
async def list_committees(assoc_id: str | None = None, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await CommitteeService(session).list(context.account, assoc_id)
    return success_response([CommitteeResponse(**row) for row in rows])


@router.post("/admin/committees", response_model=ApiResponse[IdResponse], status_code=status.HTTP_201_CREATED)
async def create_committee(payload: CommitteeCreateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        committee_id = await CommitteeService(session).create(payload, context.account)
    return success_response(IdResponse(id=committee_id), CommitteeMessage.CREATED)


@router.put("/admin/committees/{committee_id}", response_model=ApiResponse[MutationResponse])
async def update_committee(committee_id: str, payload: CommitteeUpdateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await CommitteeService(session).update(committee_id, payload, context.account)
    return success_response(MutationResponse(), CommitteeMessage.UPDATED)


@router.delete("/admin/committees/{committee_id}", response_model=ApiResponse[MutationResponse])
async def delete_committee(committee_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await CommitteeService(session).delete(committee_id, context.account)
    return success_response(MutationResponse(), CommitteeMessage.DELETED)


@router.get("/admin/associations/{association_id}/homeowners", response_model=ApiResponse[list[HomeownerResponse]])
async def list_homeowners(association_id: str, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await CommitteeService(session).homeowners(context.account, association_id)
    return success_response([HomeownerResponse(**row) for row in rows])


@router.get("/admin/homeowners", response_model=ApiResponse[list[HomeownerResponse]])
async def list_scoped_homeowners(assoc_id: str | None = None, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    service = CommitteeService(session)
    if assoc_id and assoc_id != "ALL":
        rows = await service.homeowners(context.account, assoc_id)
    else:
        rows = await service.all_homeowners(context.account)
    return success_response([HomeownerResponse(**row) for row in rows])


@router.get("/admin/committee-members", response_model=ApiResponse[list[CommitteeMemberResponse]])
async def list_committee_members(assoc_id: str | None = None, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await CommitteeService(session).list_members(context.account, assoc_id)
    return success_response([CommitteeMemberResponse(**row) for row in rows])


@router.post("/admin/committee-members", response_model=ApiResponse[MutationResponse], status_code=status.HTTP_201_CREATED)
async def assign_committee_member(payload: CommitteeMemberAssignRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await CommitteeService(session).assign_member(payload, context.account)
    return success_response(MutationResponse(), CommitteeMessage.MEMBER_ASSIGNED)


@router.put("/admin/committee-members/{committee_id}/{user_id}", response_model=ApiResponse[MutationResponse])
async def update_committee_member(committee_id: str, user_id: str, payload: CommitteeMemberUpdateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await CommitteeService(session).update_member(committee_id, user_id, payload, context.account)
    return success_response(MutationResponse(), CommitteeMessage.MEMBER_UPDATED)


@router.delete("/admin/committee-members/{committee_id}/{user_id}", response_model=ApiResponse[MutationResponse])
async def remove_committee_member(committee_id: str, user_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await CommitteeService(session).remove_member_by_user(committee_id, user_id, context.account)
    return success_response(MutationResponse(), CommitteeMessage.MEMBER_REMOVED)


@router.delete("/admin/committee-members/{member_id}", response_model=ApiResponse[MutationResponse])
async def remove_committee_member_by_id(member_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await CommitteeService(session).remove_member(member_id, context.account)
    return success_response(MutationResponse(), CommitteeMessage.MEMBER_REMOVED)


@router.get("/associations/{association_id}/committee-members", response_model=ApiResponse[list[CommitteeMemberResponse]])
async def directory_committee_members(association_id: str, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    service = CommitteeService(session)
    if association_id == "me":
        association_id = await service.member_association_id(context.account) or ""
    if not association_id:
        return success_response([])
    rows = await service.list_directory(context.account, association_id)
    return success_response([CommitteeMemberResponse(**row) for row in rows])


@router.get("/user/committees", response_model=ApiResponse[list[dict]])
async def user_committees(
    assoc_id: str | None = None,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return success_response(await CommitteeService(session).user_committees(context.account, assoc_id))


@router.get("/board_chat/{pool_type}/{pool_id}", response_model=ApiResponse[list[CommitteeChatMessageResponse]])
async def list_committee_chat(
    pool_type: str,
    pool_id: str,
    assoc_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await CommitteeService(session).chat_messages(pool_type, pool_id, assoc_id, context.account)
    return success_response([CommitteeChatMessageResponse(**row) for row in rows])


@router.post("/board_chat/{pool_type}/{pool_id}", response_model=ApiResponse[CommitteeChatMessageResponse], status_code=status.HTTP_201_CREATED)
async def send_committee_chat(
    pool_type: str,
    pool_id: str,
    assoc_id: str,
    payload: CommitteeChatMessageRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        event, recipients = await CommitteeService(session).send_chat_message(
            pool_type, pool_id, assoc_id, payload, context.account
        )
        await notify_accounts(
            session,
            recipients,
            "New Committee Message",
            f"New message in {pool_type.replace('_', ' ')} chat.",
            context.account.id,
            notification_type="committee_chat",
            entity_type=pool_type,
            entity_id=pool_id,
            action_url="/committees",
        )
    await manager.send_to_accounts(
        recipients,
        {
            "type": "committee_chat.message",
            "pool_type": pool_type,
            "pool_id": pool_id,
            "association_id": assoc_id,
            "message": jsonable_encoder(event),
        },
    )
    await publish_pending_notifications(session)
    return success_response(CommitteeChatMessageResponse(**event), "Message sent successfully")
