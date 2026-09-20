"""Dashboard reads composed from the domain services used by each role."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.announcements.service import AnnouncementService
from app.modules.auth.models import Account
from app.modules.events.service import EventService
from app.modules.meetings.service import MeetingService
from app.modules.polls.service import PollService


class DashboardService:
    """Build dashboard payloads without bypassing feature authorization rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def timeline(self, account: Account, limit: int, offset: int) -> list[dict[str, Any]]:
        """Return the legacy mixed activity feed for the current account."""
        announcements = await AnnouncementService(self.session).list(account)
        events = await EventService(self.session).list(account, scope="all")
        polls = await PollService(self.session).list(account, scope="all")
        meetings = await MeetingService(self.session).list(account)

        items: list[dict[str, Any]] = []
        items.extend(self._with_type(self._announcement_item(row), "announcement") for row in announcements)
        items.extend(
            self._with_type(row, "event")
            for row in events
            if str(row.get("status", "Published")).lower() == "published"
        )
        items.extend(
            self._with_type(row, "poll")
            for row in polls
            if str(row.get("status", "Published")).lower() == "published"
        )
        items.extend(self._with_type(row, "meeting") for row in meetings)

        items.sort(key=lambda item: self._sort_key(item.get("created_at")), reverse=True)
        return items[offset : offset + limit]

    @staticmethod
    def _announcement_item(row: dict[str, Any]) -> dict[str, Any]:
        """Expose both legacy and modular engagement field names."""
        item = dict(row)
        item["like_count"] = int(item.get("likes_count") or item.get("like_count") or 0)
        item["comment_count"] = int(item.get("comments_count") or item.get("comment_count") or 0)
        item["user_has_liked"] = bool(item.get("liked", item.get("user_has_liked", False)))
        return item

    @staticmethod
    def _with_type(row: dict[str, Any], item_type: str) -> dict[str, Any]:
        item = dict(row)
        item["item_type"] = item_type
        return item

    @staticmethod
    def _sort_key(value: Any) -> float:
        if isinstance(value, datetime):
            return value.timestamp()
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time()).timestamp()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return 0
        return 0

    async def access_code_stats(self) -> dict[str, int]:
        """Preserve the legacy `/admin/stats` payload used by admin dashboards."""
        queries = {
            "total_codes": "SELECT COUNT(*) FROM user_codes",
            "used_codes": "SELECT COUNT(*) FROM user_codes WHERE status = 'used'",
            "pending_requests": "SELECT COUNT(*) FROM code_requests WHERE status = 'pending'",
            "members": (
                "SELECT COUNT(*) FROM accounts ac JOIN roles r ON ac.role_id = r.id "
                "WHERE r.code = 'homeowner'"
            ),
            "open_update_requests": "SELECT COUNT(*) FROM update_requests WHERE status = 'open'",
        }
        return {
            name: int(await self.session.scalar(text(query)) or 0)
            for name, query in queries.items()
        }
