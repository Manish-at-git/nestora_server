"""Authorization and transactional board-member workflows."""

from datetime import date
import uuid

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.board_members.constants import BOARD_MEMBER_DIRECTORY_ROLES, BOARD_MEMBER_MANAGER_ROLES
from app.modules.board_members.messages import BoardMemberMessage
from app.modules.board_members.models import BoardMember
from app.modules.board_members.repository import BoardMemberRepository
from app.modules.board_members.schemas import BoardMemberCreateRequest


class BoardMemberService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = BoardMemberRepository(session)

    @staticmethod
    def role_code(account: Account) -> RoleCode:
        if account.role is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, BoardMemberMessage.FORBIDDEN)
        try:
            return RoleCode(account.role.code)
        except ValueError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, BoardMemberMessage.FORBIDDEN) from exc

    async def directory(self, association_id: str, account: Account) -> list[dict]:
        role = self.role_code(account)
        if role not in BOARD_MEMBER_DIRECTORY_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, BoardMemberMessage.FORBIDDEN)
        actual = await self._resolve_association(association_id, account)
        await self._require_read_access(account, actual)
        return await self.repository.directory(actual)

    async def admin_list(self, association_id: str | None, account: Account) -> list[dict]:
        self._require_manager(account)
        if association_id:
            await self._require_association_access(account, association_id)
        allowed = None if self.role_code(account) == RoleCode.SUPER_ADMIN else await self.repository.association_ids_for_admin(account.id)
        if allowed is not None and association_id is None:
            rows: list[dict] = []
            for item in allowed:
                rows.extend(await self.repository.list_members(item))
            return rows
        return await self.repository.list_members(association_id)

    async def homeowners(self, association_id: str, account: Account) -> list[dict]:
        self._require_manager_or_board(account)
        await self._require_association_access(account, association_id)
        return await self.repository.homeowners(association_id, RoleCode.HOMEOWNER.value)

    async def create(self, payload: BoardMemberCreateRequest, account: Account) -> str:
        self._require_manager(account)
        if payload.term_end_date < payload.term_start_date:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, BoardMemberMessage.INVALID_DATES)
        await self._require_association_access(account, payload.association_id)
        if not await self.repository.association_exists(payload.association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, BoardMemberMessage.INVALID_ASSOCIATION)
        if not await self.repository.account_belongs_to_association(payload.account_id, payload.association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, BoardMemberMessage.INVALID_ACCOUNT)
        if await self.repository.account_role_code(payload.account_id) != RoleCode.HOMEOWNER.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, BoardMemberMessage.INVALID_ACCOUNT)
        if await self.repository.active_membership(payload.account_id, payload.association_id):
            raise HTTPException(status.HTTP_409_CONFLICT, "This account is already an active board member.")
        board_role_id = await self.repository.role_id(RoleCode.BOARD_MEMBER.value)
        if board_role_id is None:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Board member role is not configured.")
        membership = BoardMember(
            id=str(uuid.uuid4()),
            association_id=payload.association_id,
            account_id=payload.account_id,
            term_start_date=payload.term_start_date,
            term_end_date=payload.term_end_date,
            status="active",
            created_by=account.id,
            is_deleted=False,
        )
        self.repository.add(membership)
        await self.repository.session.execute(
            text("UPDATE accounts SET role_id=:role_id WHERE account_id=:account_id"),
            {"role_id": board_role_id, "account_id": payload.account_id},
        )
        await self.repository.session.flush()
        return membership.id

    async def end_term(self, membership_id: str, account: Account) -> None:
        self._require_manager(account)
        membership = await self.repository.session.get(BoardMember, membership_id)
        if membership is None or membership.is_deleted:
            raise HTTPException(status.HTTP_404_NOT_FOUND, BoardMemberMessage.NOT_FOUND)
        await self._require_association_access(account, membership.association_id)
        homeowner_role_id = await self.repository.role_id(RoleCode.HOMEOWNER.value)
        if homeowner_role_id is None:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Homeowner role is not configured.")
        membership.status = "past"
        membership.term_end_date = date.today()
        other_active = await self.repository.session.scalar(
            text("SELECT id FROM board_members WHERE account_id=:account_id AND status='active' AND is_deleted=0 AND id<>:id LIMIT 1"),
            {"account_id": membership.account_id, "id": membership.id},
        )
        if not other_active:
            await self.repository.session.execute(
                text("UPDATE accounts SET role_id=:role_id WHERE account_id=:account_id"),
                {"role_id": homeowner_role_id, "account_id": membership.account_id},
            )
        await self.repository.session.flush()

    async def _resolve_association(self, association_id: str, account: Account) -> str:
        if association_id != "me":
            if not await self.repository.association_exists(association_id):
                raise HTTPException(status.HTTP_404_NOT_FOUND, BoardMemberMessage.INVALID_ASSOCIATION)
            return association_id
        actual = await self.repository.member_association_id(account)
        if not actual:
            raise HTTPException(status.HTTP_404_NOT_FOUND, BoardMemberMessage.INVALID_ASSOCIATION)
        return actual

    async def _require_read_access(self, account: Account, association_id: str) -> None:
        role = self.role_code(account)
        if role == RoleCode.SUPER_ADMIN:
            return
        if role == RoleCode.ADMIN:
            await self._require_association_access(account, association_id)
            return
        if await self.repository.member_association_id(account) != association_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, BoardMemberMessage.FORBIDDEN)

    async def _require_association_access(self, account: Account, association_id: str) -> None:
        role = self.role_code(account)
        if role == RoleCode.SUPER_ADMIN:
            return
        if role == RoleCode.ADMIN and association_id in await self.repository.association_ids_for_admin(account.id):
            return
        if role == RoleCode.BOARD_MEMBER and association_id == await self.repository.member_association_id(account):
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, BoardMemberMessage.INVALID_ASSOCIATION)

    def _require_manager(self, account: Account) -> None:
        if self.role_code(account) not in BOARD_MEMBER_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, BoardMemberMessage.FORBIDDEN)

    def _require_manager_or_board(self, account: Account) -> None:
        if self.role_code(account) not in BOARD_MEMBER_MANAGER_ROLES | {RoleCode.BOARD_MEMBER}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, BoardMemberMessage.FORBIDDEN)
