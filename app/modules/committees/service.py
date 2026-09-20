"""Authorization and transactional committee workflows."""

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.committees.constants import COMMITTEE_DIRECTORY_ROLES, COMMITTEE_MANAGER_ROLES
from app.modules.committees.messages import CommitteeMessage as Messages
from app.modules.committees.models import BoardCommitteeChatMessage, Committee, CommitteeMember
from app.modules.committees.repository import CommitteeRepository
from app.modules.committees.schemas import (
    CommitteeCreateRequest,
    CommitteeMemberAssignRequest,
    CommitteeMemberUpdateRequest,
    CommitteeUpdateRequest,
    CommitteeChatMessageRequest,
)


class CommitteeService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = CommitteeRepository(session)

    @staticmethod
    def role_code(account: Account) -> RoleCode:
        if account.role is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        try:
            return RoleCode(account.role.code)
        except ValueError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN) from exc

    async def list(self, account: Account, association_id: str | None = None) -> list[dict]:
        role_code = self.role_code(account)
        if role_code == RoleCode.SUPER_ADMIN:
            allowed: list[str] | None = None
        elif role_code == RoleCode.ADMIN:
            allowed = await self.repository.association_ids_for_admin(account.id)
        elif role_code in COMMITTEE_DIRECTORY_ROLES:
            member_association = await self.repository.member_association_id(account)
            allowed = [member_association] if member_association else []
        else:
            return []
        if association_id and association_id != "ALL":
            if allowed is not None and association_id not in allowed:
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
            allowed = [association_id]
        return await self.repository.list_committees(allowed)

    async def homeowners(self, account: Account, association_id: str) -> list[dict]:
        allowed = await self._allowed_associations(account)
        if allowed is not None and association_id not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        if not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.INVALID_ASSOCIATION)
        return await self.repository.list_homeowners([association_id])

    async def all_homeowners(self, account: Account) -> list[dict]:
        allowed = await self._allowed_associations(account, manager_only=True)
        return await self.repository.list_homeowners(allowed)

    async def member_association_id(self, account: Account) -> str | None:
        return await self.repository.member_association_id(account)

    async def create(self, payload: CommitteeCreateRequest, account: Account) -> str:
        association_id = await self._write_association(account, payload.association_id)
        await self._validate_members(payload.members, association_id)
        committee = Committee(
            id=str(uuid.uuid4()),
            association_id=association_id,
            name=payload.name,
            description=payload.description,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_deleted=False,
        )
        self.repository.add_committee(committee)
        await self.repository.session.flush()
        for item in payload.members:
            self.repository.add_member(
                CommitteeMember(
                    id=str(uuid.uuid4()),
                    committee_id=committee.id,
                    user_id=item.user_id,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    is_deleted=False,
                )
            )
            await self.repository.set_account_role(item.user_id, RoleCode.COMMITTEE_MEMBER)
        return committee.id

    async def update(self, committee_id: str, payload: CommitteeUpdateRequest, account: Account) -> None:
        committee = await self.repository.committee_model(committee_id)
        if committee is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        await self._require_association_access(account, committee.association_id)
        association_id = await self._write_association(account, payload.association_id)
        await self._validate_members(payload.members, association_id, committee.id)
        committee.association_id = association_id
        committee.name = payload.name
        committee.description = payload.description
        committee.start_date = payload.start_date
        committee.end_date = payload.end_date
        existing_result = await self.repository.session.execute(
            select(CommitteeMember).where(
                CommitteeMember.committee_id == committee.id, CommitteeMember.is_deleted.is_(False)
            )
        )
        existing = {member.user_id: member for member in existing_result.scalars().all()}
        requested = {item.user_id: item for item in payload.members}
        for user_id, member in existing.items():
            if user_id not in requested:
                member.is_deleted = True
                if not await self.repository.has_active_membership(user_id):
                    await self.repository.restore_homeowner_role(user_id)
        for user_id, item in requested.items():
            member = existing.get(user_id)
            if member is None:
                member = await self.repository.committee_member(committee.id, user_id, include_deleted=True)
                if member is None:
                    member = CommitteeMember(id=str(uuid.uuid4()), committee_id=committee.id, user_id=user_id)
                    self.repository.add_member(member)
                member.is_deleted = False
            member.start_date = item.start_date
            member.end_date = item.end_date
            await self.repository.set_account_role(user_id, RoleCode.COMMITTEE_MEMBER)
        await self.repository.session.flush()

    async def delete(self, committee_id: str, account: Account) -> None:
        committee = await self.repository.committee_model(committee_id)
        if committee is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        await self._require_association_access(account, committee.association_id)
        result = await self.repository.session.execute(
            select(CommitteeMember).where(
                CommitteeMember.committee_id == committee.id, CommitteeMember.is_deleted.is_(False)
            )
        )
        members = list(result.scalars().all())
        committee.is_deleted = True
        for member in members:
            member.is_deleted = True
            if not await self.repository.has_active_membership(member.user_id):
                await self.repository.restore_homeowner_role(member.user_id)
        await self.repository.session.flush()

    async def list_members(self, account: Account, association_id: str | None = None) -> list[dict]:
        allowed = await self._allowed_associations(account, manager_only=True)
        if association_id and association_id != "ALL":
            if allowed is not None and association_id not in allowed:
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
            allowed = [association_id]
        return await self.repository.list_members(allowed)

    async def list_directory(self, account: Account, association_id: str) -> list[dict]:
        role_code = self.role_code(account)
        if role_code not in COMMITTEE_DIRECTORY_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        if role_code in {RoleCode.HOMEOWNER, RoleCode.TENANT}:
            member_association = await self.repository.member_association_id(account)
            allowed = [member_association] if member_association else []
        else:
            allowed = await self._allowed_associations(account)
        if allowed is not None and association_id not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        return await self.repository.list_members([association_id])

    async def assign_member(self, payload: CommitteeMemberAssignRequest, account: Account) -> None:
        committee = await self.repository.committee_model(payload.committee_id)
        if committee is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        await self._require_association_access(account, committee.association_id)
        if not await self.repository.homeowner_in_association(payload.user_id, committee.association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.INVALID_MEMBER)
        if await self.repository.committee_member(committee.id, payload.user_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.DUPLICATE_MEMBER)
        member = await self.repository.committee_member(committee.id, payload.user_id, include_deleted=True)
        if member is None:
            member = CommitteeMember(id=str(uuid.uuid4()), committee_id=committee.id, user_id=payload.user_id)
            self.repository.add_member(member)
        member.start_date = payload.start_date
        member.end_date = payload.end_date
        member.is_deleted = False
        await self.repository.set_account_role(payload.user_id, RoleCode.COMMITTEE_MEMBER)
        await self.repository.session.flush()

    async def update_member(self, committee_id: str, user_id: str, payload: CommitteeMemberUpdateRequest, account: Account) -> None:
        member = await self.repository.committee_member(committee_id, user_id)
        if member is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.MEMBER_NOT_FOUND)
        committee = await self.repository.committee_model(committee_id)
        if committee is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        await self._require_association_access(account, committee.association_id)
        member.start_date = payload.start_date
        member.end_date = payload.end_date
        await self.repository.session.flush()

    async def remove_member(self, member_id: str, account: Account) -> None:
        member = await self.repository.member_model(member_id)
        if member is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.MEMBER_NOT_FOUND)
        await self._remove_member(member, account)

    async def remove_member_by_user(self, committee_id: str, user_id: str, account: Account) -> None:
        member = await self.repository.committee_member(committee_id, user_id)
        if member is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.MEMBER_NOT_FOUND)
        await self._remove_member(member, account)

    async def user_committees(self, account: Account, association_id: str | None = None) -> list[dict]:
        if self.role_code(account) not in {RoleCode.BOARD_MEMBER, RoleCode.COMMITTEE_MEMBER} or not account.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        rows = await self.repository.user_committees(account.user_id)
        if association_id and association_id != "ALL":
            rows = [row for row in rows if row["association_id"] == association_id]
        return rows

    async def chat_messages(self, pool_type: str, pool_id: str, association_id: str, account: Account) -> list[dict]:
        await self._require_chat_access(pool_type, pool_id, association_id, account)
        return await self.repository.chat_messages(pool_type, pool_id, association_id, account.id)

    async def send_chat_message(
        self, pool_type: str, pool_id: str, association_id: str, payload: CommitteeChatMessageRequest, account: Account
    ) -> tuple[dict, set[str]]:
        await self._require_chat_access(pool_type, pool_id, association_id, account)
        message = BoardCommitteeChatMessage(
            id=str(uuid.uuid4()),
            association_id=association_id,
            pool_type=pool_type,
            pool_id=pool_id,
            sender_id=account.id,
            message=payload.message,
            attachment_url=payload.attachment_url,
            is_deleted=False,
        )
        self.repository.add_chat_message(message)
        await self.repository.session.flush()
        event = await self.repository.chat_message(message.id)
        if event is None:
            raise RuntimeError("Persisted committee chat message could not be loaded")
        event["is_mine"] = True
        recipients = await self.repository.chat_participants(pool_type, pool_id, association_id)
        recipients.discard(account.id)
        return event, recipients

    async def _remove_member(self, member: CommitteeMember, account: Account) -> None:
        committee = await self.repository.committee_model(member.committee_id)
        if committee is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        await self._require_association_access(account, committee.association_id)
        member.is_deleted = True
        if not await self.repository.has_active_membership(member.user_id):
            await self.repository.restore_homeowner_role(member.user_id)
        await self.repository.session.flush()

    async def _validate_members(
        self, members: list, association_id: str, committee_id: str | None = None
    ) -> None:
        if len({item.user_id for item in members}) != len(members):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.DUPLICATE_MEMBER)
        for item in members:
            if not await self.repository.homeowner_in_association(item.user_id, association_id):
                existing = (
                    await self.repository.committee_member(committee_id, item.user_id)
                    if committee_id
                    else None
                )
                if existing is None:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.INVALID_MEMBER)

    async def _allowed_associations(self, account: Account, manager_only: bool = False) -> list[str] | None:
        role_code = self.role_code(account)
        if manager_only and role_code not in COMMITTEE_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        if role_code == RoleCode.SUPER_ADMIN:
            return None
        if role_code == RoleCode.ADMIN:
            return await self.repository.association_ids_for_admin(account.id)
        if role_code in {RoleCode.BOARD_MEMBER, RoleCode.COMMITTEE_MEMBER}:
            association_id = await self.repository.member_association_id(account)
            return [association_id] if association_id else []
        raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)

    async def _write_association(self, account: Account, association_id: str) -> str:
        role_code = self.role_code(account)
        if role_code == RoleCode.BOARD_MEMBER:
            association_id = await self.repository.member_association_id(account) or ""
        if role_code not in COMMITTEE_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        if not association_id or not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.INVALID_ASSOCIATION)
        await self._require_association_access(account, association_id)
        return association_id

    async def _require_association_access(self, account: Account, association_id: str) -> None:
        allowed = await self._allowed_associations(account)
        if allowed is not None and association_id not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)

    async def _require_chat_access(self, pool_type: str, pool_id: str, association_id: str, account: Account) -> None:
        if pool_type not in {"board", "committee"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported chat pool")
        if not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.INVALID_ASSOCIATION)
        await self._require_association_access(account, association_id)
        if pool_type == "committee":
            committee = await self.repository.committee_model(pool_id)
            if committee is None or committee.association_id != association_id:
                raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
