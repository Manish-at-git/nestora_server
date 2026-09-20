"""SQL access for events and their engagement records."""

from collections.abc import Iterable

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Account
from app.modules.events.models import Event, EventComment, EventLike, EventRSVP


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def association_ids_for_admin(self, account_id: str) -> list[str]:
        result = await self.session.scalars(text("SELECT association_id FROM admin_associations WHERE admin_id = :id"), {"id": account_id})
        return list(result.all())

    async def member_association_id(self, account: Account) -> str | None:
        if not account.user_id:
            return None
        return await self.session.scalar(text(
            "SELECT COALESCE(ud.association_id, b.association_id) FROM user_details ud "
            "LEFT JOIN units u ON u.id=ud.unit_id LEFT JOIN blocks b ON b.id=u.block_id "
            "WHERE ud.user_id=:uid AND ud.is_deleted=0 LIMIT 1"), {"uid": account.user_id})

    async def association_exists(self, association_id: str) -> bool:
        return bool(await self.session.scalar(text("SELECT id FROM associations WHERE id=:id AND is_deleted=0 LIMIT 1"), {"id": association_id}))

    async def list(self, association_ids: Iterable[str] | None, account_id: str, audiences: Iterable[str] | None, scope: str) -> list[dict]:
        query = (
            "SELECT e.*, COALESCE(ud.name, ac.email) AS author_name, "
            "(SELECT COUNT(*) FROM event_likes l WHERE l.event_id=e.id AND l.is_deleted=0) AS like_count, "
            "(SELECT COUNT(*) FROM event_comments c WHERE c.event_id=e.id AND c.is_deleted=0) AS comment_count, "
            "EXISTS(SELECT 1 FROM event_likes ml WHERE ml.event_id=e.id AND ml.account_id=:account_id AND ml.is_deleted=0) AS user_has_liked "
            "FROM events e LEFT JOIN accounts ac ON ac.account_id=e.created_by LEFT JOIN user_details ud ON ud.user_id=ac.user_id "
            "WHERE e.is_deleted=0"
        )
        params: dict = {"account_id": account_id}
        if association_ids is not None:
            ids = tuple(dict.fromkeys(association_ids))
            if not ids:
                return []
            query += " AND e.association_id IN :association_ids"
            params["association_ids"] = ids
        if audiences is not None:
            values = tuple(dict.fromkeys(audiences))
            if not values:
                return []
            query += " AND e.audience IN :audiences"
            params["audiences"] = values
        if scope == "past":
            query += " AND e.starts_at < NOW() ORDER BY e.starts_at DESC"
        elif scope == "upcoming":
            query += " AND e.starts_at >= NOW() ORDER BY e.starts_at ASC"
        else:
            query += " ORDER BY e.starts_at DESC"
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        if audiences is not None:
            statement = statement.bindparams(bindparam("audiences", expanding=True))
        result = await self.session.execute(statement, params)
        rows = [dict(row) for row in result.mappings().all()]
        if not rows:
            return []
        ids = tuple(row["id"] for row in rows)
        placeholders = ",".join(f":event_{i}" for i in range(len(ids)))
        id_params = {f"event_{i}": value for i, value in enumerate(ids)}
        count_rows = await self.session.execute(text(f"SELECT event_id,status,COUNT(*) c FROM event_rsvps WHERE is_deleted=0 AND event_id IN ({placeholders}) GROUP BY event_id,status"), id_params)
        counts: dict[str, dict[str, int]] = {}
        for row in count_rows.mappings():
            counts.setdefault(row["event_id"], {"going": 0, "maybe": 0, "not_going": 0})[row["status"]] = int(row["c"])
        mine = await self.session.execute(text(f"SELECT event_id,status FROM event_rsvps WHERE is_deleted=0 AND account_id=:account_id AND event_id IN ({placeholders})"), {**id_params, "account_id": account_id})
        my_status = {row["event_id"]: row["status"] for row in mine.mappings()}
        attendees = await self.session.execute(text(f"SELECT r.event_id,COALESCE(ud.name,ac.email) name FROM event_rsvps r JOIN accounts ac ON ac.account_id=r.account_id LEFT JOIN user_details ud ON ud.user_id=ac.user_id WHERE r.is_deleted=0 AND r.status='going' AND r.event_id IN ({placeholders}) ORDER BY r.updated_at DESC"), id_params)
        attendee_map: dict[str, list[str]] = {}
        for row in attendees.mappings():
            attendee_map.setdefault(row["event_id"], []).append(row["name"])
        for row in rows:
            row["user_has_liked"] = bool(row["user_has_liked"])
            row["rsvp_counts"] = counts.get(row["id"], {"going": 0, "maybe": 0, "not_going": 0})
            row["my_rsvp_status"] = my_status.get(row["id"])
            row["attendees_preview"] = attendee_map.get(row["id"], [])[:6]
        return rows

    async def get(self, event_id: str) -> Event | None:
        return await self.session.scalar(select(Event).where(Event.id == event_id, Event.is_deleted.is_(False)))

    async def rsvp(self, event_id: str, account_id: str) -> EventRSVP | None:
        return await self.session.scalar(select(EventRSVP).where(EventRSVP.event_id == event_id, EventRSVP.account_id == account_id))

    async def going_count(self, event_id: str) -> int:
        return int(await self.session.scalar(text("SELECT COUNT(*) FROM event_rsvps WHERE event_id=:id AND status='going' AND is_deleted=0"), {"id": event_id}) or 0)

    async def comments(self, event_id: str) -> list[dict]:
        result = await self.session.execute(text("SELECT c.id,c.event_id,c.account_id,c.body comment,c.created_at,COALESCE(ud.name,ac.email) author_name FROM event_comments c JOIN accounts ac ON ac.account_id=c.account_id LEFT JOIN user_details ud ON ud.user_id=ac.user_id WHERE c.event_id=:id AND c.is_deleted=0 ORDER BY c.created_at ASC"), {"id": event_id})
        return [dict(row) for row in result.mappings().all()]

    async def rsvps(self, event_id: str) -> list[dict]:
        result = await self.session.execute(text(
            "SELECT r.status,r.updated_at,ac.email,COALESCE(ud.name,ac.email) name,ud.contact_number "
            "FROM event_rsvps r JOIN accounts ac ON ac.account_id=r.account_id "
            "LEFT JOIN user_details ud ON ud.user_id=ac.user_id "
            "WHERE r.event_id=:id AND r.is_deleted=0 ORDER BY FIELD(r.status,'going','maybe','not_going'),r.updated_at DESC"
        ), {"id": event_id})
        return [dict(row) for row in result.mappings().all()]

    def add(self, event: Event) -> None: self.session.add(event)
    def add_rsvp(self, row: EventRSVP) -> None: self.session.add(row)
    def add_like(self, row: EventLike) -> None: self.session.add(row)
    def add_comment(self, row: EventComment) -> None: self.session.add(row)
