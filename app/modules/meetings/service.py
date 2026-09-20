"""Authorization and workflow rules for meetings."""

import uuid
from datetime import datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.meetings.constants import (
    MEETING_ADMIN_ROLES,
    MEETING_CREATOR_ROLES,
    MEETING_EDITOR_ROLES,
    MEETING_RSVP_ROLES,
    MeetingAudience,
    MeetingStatus,
)
from app.modules.meetings.models import Meeting, MeetingAttendance
from app.modules.meetings.repository import MeetingRepository
from app.modules.meetings.schemas import (
    MeetingAttendanceRequest,
    MeetingCreateRequest,
    MeetingDetailsRequest,
    MeetingMinutesRequest,
)


class MeetingService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = MeetingRepository(session)

    @staticmethod
    def role_code(account: Account) -> RoleCode:
        if account.role is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to meetings.")
        try:
            return RoleCode(account.role.code)
        except ValueError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to meetings.") from exc

    async def list(self, account: Account, association_id: str | None = None) -> list[dict]:
        role_code = self.role_code(account)
        if role_code in MEETING_ADMIN_ROLES:
            allowed = None if role_code == RoleCode.SUPER_ADMIN else await self.repository.association_ids_for_admin(account.id)
            if association_id and association_id != "ALL":
                if allowed is not None and association_id not in allowed:
                    raise HTTPException(status.HTTP_403_FORBIDDEN, "Association access denied.")
                return await self.repository.list(account.id, [association_id])
            return await self.repository.list(account.id, allowed)
        member = await self.repository.member_context(account)
        if role_code == RoleCode.BOARD_MEMBER and member:
            if association_id and association_id not in {"ALL", member["association_id"]}:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Association access denied.")
            return await self.repository.list(account.id, [member["association_id"]])
        if role_code in {RoleCode.HOMEOWNER, RoleCode.TENANT} and member:
            if association_id and association_id not in {"ALL", member["association_id"]}:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Association access denied.")
            return await self.repository.list(
                account.id,
                [member["association_id"]],
                audience=MeetingAudience.HOMEOWNER,
                block_id=member["block_id"],
            )
        if role_code == RoleCode.COMMITTEE_MEMBER and member:
            if association_id and association_id not in {"ALL", member["association_id"]}:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Association access denied.")
            return await self.repository.list(
                account.id,
                [member["association_id"]],
                audience=MeetingAudience.COMMITTEE_MEMBER,
                block_id=member["block_id"],
            )
        return []

    async def create(self, payload: MeetingCreateRequest, account: Account) -> None:
        role_code = self.role_code(account)
        if role_code not in MEETING_CREATOR_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only authorized association members can schedule meetings.")
        association_id = payload.association_id
        if not association_id or association_id == "me":
            if role_code != RoleCode.BOARD_MEMBER:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "association_id is required.")
            member = await self.repository.member_context(account)
            association_id = member["association_id"] if member else None
        if not association_id or not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Association not found.")
        await self._require_create_access(account, association_id)
        if payload.target_block_id and not await self.repository.block_belongs_to_association(
            payload.target_block_id,
            association_id,
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Target block does not belong to the association.")
        if not await self.repository.organizer_belongs_to_association(payload.organizer, association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Organizer must be an association board member or administrator.")
        meeting = Meeting(
            id=str(uuid.uuid4()),
            association_id=association_id,
            created_by=account.id,
            title=payload.title,
            meeting_type=payload.meeting_type,
            priority=payload.priority,
            audience=payload.audience,
            agenda=payload.agenda,
            description=payload.description,
            meeting_date=payload.meeting_date,
            meeting_time=payload.meeting_time,
            duration=payload.duration,
            venue=payload.venue,
            meeting_link=payload.meeting_link or self._generated_link(),
            organizer=payload.organizer,
            attachment_url=payload.attachment_url,
            target_block_id=payload.target_block_id,
            status=MeetingStatus.SCHEDULED,
            is_deleted=False,
        )
        self.repository.add(meeting)
        await self.repository.session.flush()
        await self.repository.notify_audience(
            association_id,
            payload.audience,
            payload.target_block_id,
            f"New Meeting: {payload.title}",
            f"A new {payload.meeting_type} has been scheduled for {payload.meeting_date} at {payload.meeting_time}.",
            account.id,
            meeting.id,
        )

    async def update_details(self, meeting_id: str, payload: MeetingDetailsRequest, account: Account) -> None:
        await self._require_editor(account)
        meeting = await self._get_meeting(meeting_id)
        self._check_edit_window(meeting.created_at)
        if payload.target_block_id and not await self.repository.block_belongs_to_association(payload.target_block_id, meeting.association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Target block does not belong to the association.")
        if not await self.repository.organizer_belongs_to_association(payload.organizer, meeting.association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Organizer must be an association board member or administrator.")
        for field in ("title", "meeting_type", "priority", "audience", "agenda", "description", "meeting_date", "meeting_time", "duration", "venue", "meeting_link", "organizer"):
            setattr(meeting, field, getattr(payload, field))
        meeting.target_block_id = payload.target_block_id
        await self.repository.session.flush()

    async def add_minutes(self, meeting_id: str, payload: MeetingMinutesRequest, account: Account) -> None:
        await self._require_editor(account)
        meeting = await self._get_meeting(meeting_id)
        meeting.meeting_minutes = payload.meeting_minutes
        meeting.discussed_topic = payload.discussed_topic
        meeting.status = MeetingStatus.COMPLETED
        await self.repository.session.flush()

    async def delete(self, meeting_id: str, account: Account) -> None:
        await self._require_editor(account)
        meeting = await self._get_meeting(meeting_id)
        meeting.is_deleted = True
        await self.repository.session.flush()

    async def update_attendance(self, meeting_id: str, payload: MeetingAttendanceRequest, account: Account) -> None:
        if self.role_code(account) not in MEETING_RSVP_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "RSVP is not available for this account.")
        if payload.status not in {"Yes", "No", "Maybe"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid attendance status.")
        meeting = await self._get_meeting(meeting_id)
        member = await self.repository.member_context(account)
        if not member or member["association_id"] != meeting.association_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Meeting access denied.")
        meeting_datetime = datetime.combine(meeting.meeting_date, meeting.meeting_time)
        if (meeting_datetime - datetime.now()).total_seconds() < 24 * 60 * 60:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "RSVP is locked within 24 hours of the meeting.")
        attendance = await self.repository.attendance(meeting_id, account.id)
        if attendance:
            attendance.status = payload.status
        else:
            self.repository.add_attendance(MeetingAttendance(id=str(uuid.uuid4()), meeting_id=meeting_id, account_id=account.id, status=payload.status, is_deleted=False))
        await self.repository.session.flush()

    async def organizers(self, association_id: str, account: Account) -> list[dict]:
        await self._require_association_read(account, association_id)
        return await self.repository.organizers(association_id)

    async def blocks(self, association_id: str, account: Account) -> list[dict]:
        await self._require_association_read(account, association_id)
        return await self.repository.blocks(association_id)

    async def _get_meeting(self, meeting_id: str) -> Meeting:
        meeting = await self.repository.get(meeting_id)
        if meeting is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Meeting not found.")
        if isinstance(meeting.meeting_time, timedelta):
            total_seconds = int(meeting.meeting_time.total_seconds()) % (24 * 60 * 60)
            meeting.meeting_time = time(
                total_seconds // 3600,
                (total_seconds % 3600) // 60,
                total_seconds % 60,
            )
        return meeting

    async def _require_editor(self, account: Account) -> None:
        if self.role_code(account) not in MEETING_EDITOR_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can edit meetings.")

    async def _require_create_access(self, account: Account, association_id: str) -> None:
        role_code = self.role_code(account)
        if role_code == RoleCode.SUPER_ADMIN:
            return
        if role_code == RoleCode.ADMIN:
            if association_id not in await self.repository.association_ids_for_admin(account.id):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Association access denied.")
            return
        if role_code == RoleCode.BOARD_MEMBER:
            member = await self.repository.member_context(account)
            if not member or member["association_id"] != association_id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Association access denied.")
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Meeting creation is not available for this account.")

    async def _require_association_read(self, account: Account, association_id: str) -> None:
        role_code = self.role_code(account)
        if role_code == RoleCode.SUPER_ADMIN:
            return
        if role_code in MEETING_ADMIN_ROLES:
            if association_id not in await self.repository.association_ids_for_admin(account.id):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Association access denied.")
            return
        member = await self.repository.member_context(account)
        if not member or member["association_id"] != association_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Association access denied.")

    @staticmethod
    def _check_edit_window(created_at: datetime) -> None:
        if (datetime.now(created_at.tzinfo) - created_at).total_seconds() > 2 * 60 * 60:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Edit time limit (2 hours) has expired.")

    @staticmethod
    def _generated_link() -> str:
        return f"https://meet.google.com/{uuid.uuid4().hex[:10]}"
