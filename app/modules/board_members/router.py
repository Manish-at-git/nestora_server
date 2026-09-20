"""HTTP routes for board-member nominations, terms, and directory lookup."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.board_members.messages import BoardMemberMessage
from app.modules.board_members.schemas import (
    BoardMemberCreateRequest, BoardMemberCreateResponse, BoardMemberListResponse,
    BoardMemberMutationResponse, BoardMemberResponse, HomeownerListResponse, HomeownerResponse,
)
from app.modules.board_members.service import BoardMemberService

router = APIRouter(tags=["Board Members"])


@router.get("/admin/board-members", response_model=BoardMemberListResponse)
async def admin_board_members(assoc_id: str | None = None, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await BoardMemberService(session).admin_list(assoc_id, context.account)
    return success_response([BoardMemberResponse(**row) for row in rows])


@router.get("/admin/associations/{association_id}/homeowners", response_model=HomeownerListResponse)
async def association_homeowners(association_id: str, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await BoardMemberService(session).homeowners(association_id, context.account)
    return success_response([HomeownerResponse(**row) for row in rows])


@router.post("/admin/board-members", response_model=ApiResponse[BoardMemberCreateResponse], status_code=status.HTTP_201_CREATED)
async def create_board_member(payload: BoardMemberCreateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        membership_id = await BoardMemberService(session).create(payload, context.account)
    return success_response(BoardMemberCreateResponse(id=membership_id), BoardMemberMessage.CREATED)


@router.put("/admin/board-members/{membership_id}/end-term", response_model=ApiResponse[BoardMemberMutationResponse])
async def end_board_member_term(membership_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await BoardMemberService(session).end_term(membership_id, context.account)
    return success_response(BoardMemberMutationResponse(), BoardMemberMessage.TERM_ENDED)
