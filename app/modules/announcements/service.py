"""Authorization and transactional announcement workflows."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.announcements.constants import (
    ANNOUNCEMENT_MANAGER_ROLES,
    AnnouncementAudience,
)
from app.modules.announcements.messages import AnnouncementMessage as Messages
from app.modules.announcements.models import Announcement, AnnouncementComment, AnnouncementLike
from app.modules.announcements.repository import AnnouncementRepository
from app.modules.announcements.schemas import AnnouncementCommentRequest, AnnouncementCreateRequest
from app.modules.auth.models import Account
from app.modules.notifications.service import notify_association_audience


class AnnouncementService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AnnouncementRepository(session)

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
        audiences: tuple[str, ...] | None = None
        if role_code == RoleCode.SUPER_ADMIN:
            allowed: list[str] | None = None
        elif role_code == RoleCode.ADMIN:
            allowed = await self.repository.association_ids_for_admin(account.id)
        else:
            member_association = await self.repository.member_association_id(account)
            allowed = [member_association] if member_association else []
            audiences = self._audiences_for_role(role_code)

        if association_id and association_id != "ALL":
            if allowed is not None and association_id not in allowed:
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
            if not await self.repository.association_exists(association_id):
                raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.INVALID_ASSOCIATION)
            allowed = [association_id]
        return await self.repository.list(allowed, account.id, audiences)

    async def create(self, payload: AnnouncementCreateRequest, account: Account) -> str:
        association_id = await self._write_association(account, payload.association_id)
        announcement = Announcement(
            id=str(uuid.uuid4()),
            association_id=association_id,
            title=payload.title,
            body=payload.body,
            category=payload.category.value,
            pinned=payload.pinned,
            audience=payload.audience,
            attachment_url=payload.attachment_url,
            created_by=account.id,
            is_deleted=False,
        )
        self.repository.add_announcement(announcement)
        await self.repository.session.flush()
        await notify_association_audience(
            self.repository.session,
            association_id,
            announcement.audience,
            f"New Announcement: {announcement.title}",
            announcement.body,
            account.id,
            notification_type="announcement",
            entity_type="announcement",
            entity_id=announcement.id,
            action_url="/announcements",
        )
        return announcement.id

    async def update(self, announcement_id: str, payload: AnnouncementCreateRequest, account: Account) -> None:
        announcement = await self._authorized_manager_announcement(announcement_id, account)
        self._require_board_window(announcement, account)
        announcement.title = payload.title
        announcement.body = payload.body
        announcement.category = payload.category.value
        announcement.pinned = payload.pinned
        announcement.audience = payload.audience
        announcement.attachment_url = payload.attachment_url
        await self.repository.session.flush()

    async def delete(self, announcement_id: str, account: Account) -> None:
        announcement = await self._authorized_manager_announcement(announcement_id, account)
        self._require_board_window(announcement, account)
        announcement.is_deleted = True
        await self.repository.session.flush()

    async def toggle_like(self, announcement_id: str, account: Account) -> bool:
        announcement = await self._authorized_announcement(announcement_id, account)
        like = await self.repository.like(announcement.id, account.id, include_deleted=True)
        if like is None:
            self.repository.add_like(
                AnnouncementLike(
                    id=str(uuid.uuid4()),
                    announcement_id=announcement.id,
                    account_id=account.id,
                    is_deleted=False,
                )
            )
            liked = True
        else:
            like.is_deleted = not like.is_deleted
            liked = not like.is_deleted
        await self.repository.session.flush()
        return liked

    async def comments(self, announcement_id: str, account: Account) -> list[dict]:
        announcement = await self._authorized_announcement(announcement_id, account)
        return await self.repository.comments(announcement.id)

    async def add_comment(
        self, announcement_id: str, payload: AnnouncementCommentRequest, account: Account
    ) -> str:
        announcement = await self._authorized_announcement(announcement_id, account)
        comment = AnnouncementComment(
            id=str(uuid.uuid4()),
            announcement_id=announcement.id,
            account_id=account.id,
            comment=payload.comment,
            is_deleted=False,
        )
        self.repository.add_comment(comment)
        await self.repository.session.flush()
        return comment.id

    async def _authorized_announcement(self, announcement_id: str, account: Account) -> Announcement:
        announcement = await self.repository.announcement_model(announcement_id)
        if announcement is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        await self._require_association_access(account, announcement.association_id)
        role_code = self.role_code(account)
        if role_code not in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}:
            audiences = self._audiences_for_role(role_code)
            if audiences is not None and announcement.audience not in audiences:
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        return announcement

    async def _authorized_manager_announcement(self, announcement_id: str, account: Account) -> Announcement:
        announcement = await self.repository.announcement_model(announcement_id)
        if announcement is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        if self.role_code(account) not in ANNOUNCEMENT_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        await self._require_association_access(account, announcement.association_id)
        return announcement

    async def _write_association(self, account: Account, association_id: str | None) -> str:
        role_code = self.role_code(account)
        if role_code not in ANNOUNCEMENT_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        if role_code == RoleCode.BOARD_MEMBER and (not association_id or association_id == "me"):
            association_id = await self.repository.member_association_id(account)
        if not association_id or association_id == "me":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.INVALID_ASSOCIATION)
        if not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.INVALID_ASSOCIATION)
        await self._require_association_access(account, association_id)
        return association_id

    async def _require_association_access(self, account: Account, association_id: str | None) -> None:
        if not association_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        role_code = self.role_code(account)
        if role_code == RoleCode.SUPER_ADMIN:
            return
        if role_code == RoleCode.ADMIN:
            if association_id not in await self.repository.association_ids_for_admin(account.id):
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
            return
        if await self.repository.member_association_id(account) != association_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)

    @staticmethod
    def _audiences_for_role(role_code: RoleCode) -> tuple[str, ...] | None:
        if role_code == RoleCode.HOMEOWNER or role_code == RoleCode.TENANT:
            return (AnnouncementAudience.ALL, AnnouncementAudience.HOMEOWNERS, AnnouncementAudience.HOMEOWNER)
        if role_code == RoleCode.COMMITTEE_MEMBER:
            return (
                AnnouncementAudience.ALL,
                AnnouncementAudience.COMMITTEE_MEMBERS,
                AnnouncementAudience.COMMITTEE_MEMBER,
            )
        if role_code == RoleCode.BOARD_MEMBER:
            return None
        return (AnnouncementAudience.ALL,)

    def _require_board_window(self, announcement: Announcement, account: Account) -> None:
        if self.role_code(account) != RoleCode.BOARD_MEMBER or announcement.created_at is None:
            return
        created_at = announcement.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created_at > timedelta(hours=2):
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.BOARD_WINDOW_EXPIRED)
