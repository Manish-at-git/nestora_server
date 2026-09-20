"""Authorization and transactional poll workflows."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.polls.constants import POLL_MANAGER_ROLES, POLL_VOTER_ROLES, PollVisibility
from app.modules.polls.messages import PollMessage
from app.modules.polls.models import Poll, PollComment, PollLike, PollOption, PollVote
from app.modules.polls.repository import PollRepository
from app.modules.polls.schemas import PollCommentRequest, PollCreateRequest, PollVoteRequest
from app.modules.notifications.service import notify_association_audience


class PollService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = PollRepository(session)

    @staticmethod
    def role_code(account: Account) -> RoleCode:
        if account.role is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, PollMessage.FORBIDDEN)
        try:
            return RoleCode(account.role.code)
        except ValueError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, PollMessage.FORBIDDEN) from exc

    async def list(self, account: Account, association_id: str | None = None, scope: str = "all") -> list[dict]:
        role = self.role_code(account)
        if role == RoleCode.SUPER_ADMIN:
            allowed = None
        elif role == RoleCode.ADMIN:
            allowed = await self.repository.association_ids_for_admin(account.id)
        else:
            member = await self.repository.member_association_id(account)
            allowed = [member] if member else []
        if association_id and association_id != "ALL":
            if allowed is not None and association_id not in allowed:
                raise HTTPException(status.HTTP_403_FORBIDDEN, PollMessage.FORBIDDEN)
            if not await self.repository.association_exists(association_id):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Association not found.")
            allowed = [association_id]
        manager = role in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}
        visibility = None if manager else self._visibility(role)
        effective_scope = (scope or "all").lower() if manager else "member"
        return await self.repository.list(allowed, account.id, visibility, effective_scope)

    async def create(self, payload: PollCreateRequest, account: Account) -> str:
        role = self.role_code(account)
        if role not in POLL_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, PollMessage.FORBIDDEN)
        association_id = payload.association_id
        if not association_id or association_id in {"ALL", "all"}:
            association_id = await self.repository.member_association_id(account) if role == RoleCode.BOARD_MEMBER else None
        if not association_id or not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "association_id is required.")
        await self._require_association_access(account, association_id)
        poll = Poll(id=str(uuid.uuid4()), association_id=association_id, created_by=account.id, **payload.model_dump(exclude={"association_id", "options"}))
        self.repository.add(poll)
        for option in payload.options:
            self.repository.add(PollOption(id=str(uuid.uuid4()), poll_id=poll.id, option_text=option.text, is_deleted=False))
        await self.repository.session.flush()
        if poll.status.strip().lower() == "published":
            await notify_association_audience(
                self.repository.session,
                association_id,
                poll.visibility,
                "New Poll",
                poll.question,
                account.id,
                notification_type="poll",
                entity_type="poll",
                entity_id=poll.id,
                action_url="/polls",
            )
        return poll.id

    async def update(self, poll_id: str, payload: PollCreateRequest, account: Account) -> None:
        poll = await self._manager_poll(poll_id, account)
        self._check_window(poll, account)
        was_published = poll.status.strip().lower() == "published"
        for field, value in payload.model_dump(exclude={"association_id", "options"}).items():
            setattr(poll, field, value)
        current = await self.repository.session.scalars(
            select(PollOption).where(PollOption.poll_id == poll.id, PollOption.is_deleted.is_(False))
        )
        current_options = current.all()
        for option in current_options:
            option.is_deleted = True
            old_votes = await self.repository.session.scalars(
                select(PollVote).where(PollVote.poll_id == poll.id, PollVote.option_id == option.id, PollVote.is_deleted.is_(False))
            )
            for vote in old_votes.all():
                vote.is_deleted = True
        for option in payload.options:
            self.repository.add(PollOption(id=str(uuid.uuid4()), poll_id=poll.id, option_text=option.text, is_deleted=False))
        await self.repository.session.flush()
        if not was_published and poll.status.strip().lower() == "published":
            await notify_association_audience(
                self.repository.session,
                poll.association_id,
                poll.visibility,
                "New Poll",
                poll.question,
                account.id,
                notification_type="poll",
                entity_type="poll",
                entity_id=poll.id,
                action_url="/polls",
            )

    async def delete(self, poll_id: str, account: Account) -> None:
        poll = await self._manager_poll(poll_id, account)
        self._check_window(poll, account)
        poll.is_deleted = True
        await self.repository.session.flush()

    async def vote(self, poll_id: str, payload: PollVoteRequest, account: Account) -> None:
        if self.role_code(account) not in POLL_VOTER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, PollMessage.FORBIDDEN)
        poll = await self._authorized_poll(poll_id, account)
        if poll.status != "Published" or (poll.end_date and poll.end_date < datetime.now(poll.end_date.tzinfo)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Poll is not active.")
        option_ids = list(dict.fromkeys(payload.option_ids))
        if not poll.is_multiple_choice and len(option_ids) > 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Multiple selection is not allowed for this poll.")
        for option_id in option_ids:
            if await self.repository.option(option_id, poll.id) is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "One or more options are invalid.")
        existing = await self.repository.session.scalars(
            select(PollVote).where(PollVote.poll_id == poll.id, PollVote.account_id == account.id)
        )
        for vote in existing.all():
            vote.is_deleted = True
        for option_id in option_ids:
            row = await self.repository.vote(poll.id, option_id, account.id)
            if row is None:
                self.repository.add(PollVote(poll_id=poll.id, option_id=option_id, account_id=account.id, is_deleted=False))
            else:
                row.is_deleted = False
        await self.repository.session.flush()

    async def like(self, poll_id: str, account: Account) -> bool:
        await self._authorized_poll(poll_id, account)
        row = await self.repository.session.get(PollLike, {"poll_id": poll_id, "account_id": account.id})
        if row is None:
            self.repository.add(PollLike(poll_id=poll_id, account_id=account.id, is_deleted=False))
            liked = True
        else:
            row.is_deleted = not row.is_deleted
            liked = not row.is_deleted
        await self.repository.session.flush()
        return liked

    async def comments(self, poll_id: str, account: Account) -> list[dict]:
        await self._authorized_poll(poll_id, account)
        return await self.repository.comments(poll_id)

    async def add_comment(self, poll_id: str, payload: PollCommentRequest, account: Account) -> str:
        await self._authorized_poll(poll_id, account)
        row = PollComment(id=str(uuid.uuid4()), poll_id=poll_id, account_id=account.id, content=payload.comment, is_deleted=False)
        self.repository.add(row)
        await self.repository.session.flush()
        return row.id

    async def _authorized_poll(self, poll_id: str, account: Account) -> Poll:
        poll = await self.repository.get(poll_id)
        if poll is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, PollMessage.NOT_FOUND)
        role = self.role_code(account)
        if role == RoleCode.ADMIN:
            if poll.association_id not in await self.repository.association_ids_for_admin(account.id):
                raise HTTPException(status.HTTP_403_FORBIDDEN, PollMessage.FORBIDDEN)
        elif role != RoleCode.SUPER_ADMIN:
            if await self.repository.member_association_id(account) != poll.association_id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, PollMessage.FORBIDDEN)
            if poll.visibility not in self._visibility(role):
                raise HTTPException(status.HTTP_403_FORBIDDEN, PollMessage.FORBIDDEN)
        return poll

    async def _manager_poll(self, poll_id: str, account: Account) -> Poll:
        if self.role_code(account) not in POLL_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, PollMessage.FORBIDDEN)
        poll = await self.repository.get(poll_id)
        if poll is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, PollMessage.NOT_FOUND)
        await self._require_association_access(account, poll.association_id)
        return poll

    async def _require_association_access(self, account: Account, association_id: str) -> None:
        role = self.role_code(account)
        if role == RoleCode.SUPER_ADMIN:
            return
        if role == RoleCode.ADMIN and association_id in await self.repository.association_ids_for_admin(account.id):
            return
        if role == RoleCode.BOARD_MEMBER and association_id == await self.repository.member_association_id(account):
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, PollMessage.FORBIDDEN)

    @staticmethod
    def _visibility(role: RoleCode) -> tuple[str, ...]:
        if role in {RoleCode.HOMEOWNER, RoleCode.TENANT}:
            return (PollVisibility.ALL, PollVisibility.HOMEOWNER, PollVisibility.HOMEOWNERS)
        if role == RoleCode.COMMITTEE_MEMBER:
            return (PollVisibility.ALL, PollVisibility.COMMITTEE_MEMBER, PollVisibility.COMMITTEE_MEMBERS)
        if role == RoleCode.BOARD_MEMBER:
            return (PollVisibility.ALL, PollVisibility.BOARD_MEMBER, PollVisibility.BOARD_MEMBERS)
        return (PollVisibility.ALL,)

    def _check_window(self, poll: Poll, account: Account) -> None:
        if self.role_code(account) != RoleCode.BOARD_MEMBER or not poll.created_at:
            return
        created = poll.created_at.replace(tzinfo=timezone.utc) if poll.created_at.tzinfo is None else poll.created_at
        if datetime.now(timezone.utc) - created > timedelta(hours=2):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Board members cannot edit polls after 2 hours.")
