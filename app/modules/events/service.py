"""Authorization and transactional event workflows."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.events.constants import EVENT_MANAGER_ROLES, EVENT_RSVP_ROLES, EventAudience
from app.modules.events.messages import EventMessage
from app.modules.events.models import Event, EventComment, EventLike, EventRSVP
from app.modules.events.repository import EventRepository
from app.modules.events.schemas import EventCommentRequest, EventCreateRequest, RSVPRequest
from app.modules.notifications.service import notify_association_audience


class EventService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = EventRepository(session)

    @staticmethod
    def role_code(account: Account) -> RoleCode:
        if account.role is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, EventMessage.FORBIDDEN)
        try:
            return RoleCode(account.role.code)
        except ValueError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, EventMessage.FORBIDDEN) from exc

    async def list(self, account: Account, scope: str = "upcoming", association_id: str | None = None) -> list[dict]:
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
                raise HTTPException(status.HTTP_403_FORBIDDEN, EventMessage.FORBIDDEN)
            if not await self.repository.association_exists(association_id):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Association not found.")
            allowed = [association_id]
        audiences = None if role in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.BOARD_MEMBER} else self._audiences(role)
        return await self.repository.list(allowed, account.id, audiences, scope.lower() if scope else "upcoming")

    async def create(self, payload: EventCreateRequest, account: Account) -> str:
        role = self.role_code(account)
        if role not in EVENT_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, EventMessage.FORBIDDEN)
        association_id = payload.association_id
        if not association_id or association_id == "me":
            association_id = await self.repository.member_association_id(account) if role == RoleCode.BOARD_MEMBER else None
        if not association_id or not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "association_id is required.")
        await self._require_association_access(account, association_id)
        self._validate_dates(payload)
        event = Event(
            id=str(uuid.uuid4()),
            association_id=association_id,
            created_by=account.id,
            **payload.model_dump(exclude={"association_id", "send_notifications"}),
        )
        self.repository.add(event)
        await self.repository.session.flush()
        if payload.send_notifications and event.status.strip().lower() == "published":
            await notify_association_audience(
                self.repository.session,
                association_id,
                event.audience,
                f"New Event: {event.title}",
                f"{event.title} is scheduled for {event.starts_at}.",
                account.id,
                notification_type="event",
                entity_type="event",
                entity_id=event.id,
                action_url="/events",
            )
        return event.id

    async def update(self, event_id: str, payload: EventCreateRequest, account: Account) -> None:
        event = await self._manager_event(event_id, account)
        self._check_window(event, account)
        self._validate_dates(payload)
        was_published = event.status.strip().lower() == "published"
        for field, value in payload.model_dump(exclude={"association_id", "send_notifications"}).items():
            setattr(event, field, value)
        await self.repository.session.flush()
        if (
            payload.send_notifications
            and not was_published
            and event.status.strip().lower() == "published"
        ):
            await notify_association_audience(
                self.repository.session,
                event.association_id,
                event.audience,
                f"New Event: {event.title}",
                f"{event.title} is scheduled for {event.starts_at}.",
                account.id,
                notification_type="event",
                entity_type="event",
                entity_id=event.id,
                action_url="/events",
            )

    async def delete(self, event_id: str, account: Account) -> None:
        event = await self._manager_event(event_id, account)
        self._check_window(event, account)
        event.is_deleted = True
        await self.repository.session.flush()

    async def rsvp(self, event_id: str, payload: RSVPRequest, account: Account) -> str:
        if self.role_code(account) not in EVENT_RSVP_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, EventMessage.FORBIDDEN)
        event = await self._authorized_event(event_id, account)
        row = await self.repository.rsvp(event.id, account.id)
        if payload.status.value == "going" and event.max_capacity and (row is None or row.is_deleted or row.status != "going"):
            if await self.repository.going_count(event.id) >= event.max_capacity:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "This event has reached capacity.")
        if row is None:
            row = EventRSVP(id=str(uuid.uuid4()), event_id=event.id, account_id=account.id, status=payload.status.value, is_deleted=False)
            self.repository.add_rsvp(row)
        else:
            row.status = payload.status.value
            row.is_deleted = False
        await self.repository.session.flush()
        return payload.status.value

    async def clear_rsvp(self, event_id: str, account: Account) -> None:
        row = await self.repository.rsvp(event_id, account.id)
        if row:
            row.is_deleted = True
            await self.repository.session.flush()

    async def admin_rsvps(self, event_id: str, account: Account) -> dict:
        event = await self._manager_event(event_id, account)
        rows = await self.repository.rsvps(event.id)
        counts = {"going": 0, "maybe": 0, "not_going": 0}
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return {"event": {"id": event.id, "title": event.title}, "counts": counts, "rsvps": rows}

    async def like(self, event_id: str, account: Account) -> bool:
        await self._authorized_event(event_id, account)
        row = await self.repository.session.get(EventLike, {"event_id": event_id, "account_id": account.id})
        if row is None:
            self.repository.add_like(EventLike(event_id=event_id, account_id=account.id, is_deleted=False))
            liked = True
        else:
            row.is_deleted = not row.is_deleted
            liked = not row.is_deleted
        await self.repository.session.flush()
        return liked

    async def comments(self, event_id: str, account: Account) -> list[dict]:
        await self._authorized_event(event_id, account)
        return await self.repository.comments(event_id)

    async def add_comment(self, event_id: str, payload: EventCommentRequest, account: Account) -> str:
        await self._authorized_event(event_id, account)
        row = EventComment(id=str(uuid.uuid4()), event_id=event_id, account_id=account.id, body=payload.comment, is_deleted=False)
        self.repository.add_comment(row)
        await self.repository.session.flush()
        return row.id

    async def _authorized_event(self, event_id: str, account: Account) -> Event:
        event = await self.repository.get(event_id)
        if event is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, EventMessage.NOT_FOUND)
        role = self.role_code(account)
        if role not in {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}:
            if await self.repository.member_association_id(account) != event.association_id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, EventMessage.FORBIDDEN)
            audiences = self._audiences(role)
            if audiences is not None and event.audience not in audiences:
                raise HTTPException(status.HTTP_403_FORBIDDEN, EventMessage.FORBIDDEN)
        return event

    async def _manager_event(self, event_id: str, account: Account) -> Event:
        if self.role_code(account) not in EVENT_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, EventMessage.FORBIDDEN)
        event = await self.repository.get(event_id)
        if event is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, EventMessage.NOT_FOUND)
        await self._require_association_access(account, event.association_id)
        return event

    async def _require_association_access(self, account: Account, association_id: str) -> None:
        role = self.role_code(account)
        if role == RoleCode.SUPER_ADMIN:
            return
        if role == RoleCode.ADMIN and association_id in await self.repository.association_ids_for_admin(account.id):
            return
        if role == RoleCode.BOARD_MEMBER and association_id == await self.repository.member_association_id(account):
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, EventMessage.FORBIDDEN)

    @staticmethod
    def _audiences(role: RoleCode) -> tuple[str, ...]:
        if role in {RoleCode.HOMEOWNER, RoleCode.TENANT}:
            return (EventAudience.ALL, EventAudience.HOMEOWNER, EventAudience.HOMEOWNERS)
        if role == RoleCode.COMMITTEE_MEMBER:
            return (EventAudience.ALL, EventAudience.COMMITTEE_MEMBER, EventAudience.COMMITTEE_MEMBERS)
        return (EventAudience.ALL,)

    @staticmethod
    def _validate_dates(payload: EventCreateRequest) -> None:
        if payload.ends_at and payload.ends_at < payload.starts_at:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "End time must be after start time.")

    def _check_window(self, event: Event, account: Account) -> None:
        if self.role_code(account) == RoleCode.BOARD_MEMBER and event.created_at:
            created = event.created_at.replace(tzinfo=timezone.utc) if event.created_at.tzinfo is None else event.created_at
            if datetime.now(timezone.utc) - created > timedelta(hours=2):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Board members cannot edit events after 2 hours.")
