"""SQL access for polls, options, votes, likes, and comments."""

from collections.abc import Iterable

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Account
from app.modules.polls.models import Poll, PollComment, PollLike, PollOption, PollVote


class PollRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def association_ids_for_admin(self, account_id: str) -> list[str]:
        result = await self.session.scalars(text("SELECT association_id FROM admin_associations WHERE admin_id=:id"), {"id": account_id})
        return list(result.all())

    async def member_association_id(self, account: Account) -> str | None:
        if not account.user_id:
            return None
        return await self.session.scalar(text(
            "SELECT COALESCE(ud.association_id,b.association_id) FROM user_details ud "
            "LEFT JOIN units u ON u.id=ud.unit_id LEFT JOIN blocks b ON b.id=u.block_id "
            "WHERE ud.user_id=:uid AND ud.is_deleted=0 LIMIT 1"), {"uid": account.user_id})

    async def association_exists(self, association_id: str) -> bool:
        return bool(await self.session.scalar(text("SELECT id FROM associations WHERE id=:id AND is_deleted=0 LIMIT 1"), {"id": association_id}))

    async def list(self, association_ids: Iterable[str] | None, account_id: str, visibility: Iterable[str] | None, scope: str) -> list[dict]:
        query = (
            "SELECT p.*,COALESCE(ud.name,e.name,a.email) author_name,"
            "(SELECT COUNT(*) FROM poll_likes l WHERE l.poll_id=p.id AND l.is_deleted=0) like_count,"
            "EXISTS(SELECT 1 FROM poll_likes ml WHERE ml.poll_id=p.id AND ml.account_id=:account_id AND ml.is_deleted=0) user_has_liked,"
            "(SELECT COUNT(*) FROM poll_comments c WHERE c.poll_id=p.id AND c.is_deleted=0) comment_count "
            "FROM polls p LEFT JOIN accounts a ON a.account_id=p.created_by "
            "LEFT JOIN user_details ud ON ud.user_id=a.user_id LEFT JOIN employees e ON e.employee_id=a.employee_id "
            "WHERE p.is_deleted=0"
        )
        params: dict = {"account_id": account_id}
        if association_ids is not None:
            ids = tuple(dict.fromkeys(association_ids))
            if not ids:
                return []
            query += " AND p.association_id IN :association_ids"
            params["association_ids"] = ids
        if visibility is not None:
            values = tuple(dict.fromkeys(visibility))
            if not values:
                return []
            query += " AND p.visibility IN :visibility"
            params["visibility"] = values
        if scope == "active":
            query += " AND p.status='Published' AND (p.end_date IS NULL OR p.end_date >= NOW())"
        elif scope == "closed":
            query += " AND (p.status='Closed' OR (p.end_date IS NOT NULL AND p.end_date < NOW()))"
        elif scope == "draft":
            query += " AND p.status='Draft'"
        elif scope == "member":
            query += " AND p.status='Published'"
        elif scope != "all":
            query += " AND p.status='Published'"
        query += " ORDER BY p.created_at DESC"
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        if visibility is not None:
            statement = statement.bindparams(bindparam("visibility", expanding=True))
        rows = [dict(row) for row in (await self.session.execute(statement, params)).mappings().all()]
        for row in rows:
            row["user_has_liked"] = bool(row["user_has_liked"])
            options = await self.options(row["id"])
            votes = await self.votes(row["id"])
            total = len({vote["account_id"] for vote in votes})
            mine = [vote["option_id"] for vote in votes if vote["account_id"] == account_id]
            for option in options:
                count = sum(1 for vote in votes if vote["option_id"] == option["id"])
                option.update({"text": option["option_text"], "vote_count": count, "vote_percentage": round(count * 100 / total) if total else 0})
            row.update({"options": options, "total_votes": total, "my_votes": mine})
        return rows

    async def options(self, poll_id: str) -> list[dict]:
        result = await self.session.execute(text("SELECT id,poll_id,option_text,created_at FROM poll_options WHERE poll_id=:id AND is_deleted=0 ORDER BY created_at ASC"), {"id": poll_id})
        return [dict(row) for row in result.mappings().all()]

    async def votes(self, poll_id: str) -> list[dict]:
        result = await self.session.execute(text("SELECT option_id,account_id FROM poll_votes WHERE poll_id=:id AND is_deleted=0"), {"id": poll_id})
        return [dict(row) for row in result.mappings().all()]

    async def comments(self, poll_id: str) -> list[dict]:
        result = await self.session.execute(text(
            "SELECT c.id,c.poll_id,c.account_id,c.content,c.content comment,c.created_at,COALESCE(ud.name,e.name,a.email) author_name "
            "FROM poll_comments c JOIN accounts a ON a.account_id=c.account_id LEFT JOIN user_details ud ON ud.user_id=a.user_id "
            "LEFT JOIN employees e ON e.employee_id=a.employee_id WHERE c.poll_id=:id AND c.is_deleted=0 ORDER BY c.created_at ASC"), {"id": poll_id})
        return [dict(row) for row in result.mappings().all()]

    async def get(self, poll_id: str) -> Poll | None:
        return await self.session.scalar(select(Poll).where(Poll.id == poll_id, Poll.is_deleted.is_(False)))

    async def option(self, option_id: str, poll_id: str) -> PollOption | None:
        return await self.session.scalar(select(PollOption).where(PollOption.id == option_id, PollOption.poll_id == poll_id, PollOption.is_deleted.is_(False)))

    async def vote(self, poll_id: str, option_id: str, account_id: str) -> PollVote | None:
        return await self.session.get(PollVote, {"poll_id": poll_id, "option_id": option_id, "account_id": account_id})

    def add(self, row) -> None: self.session.add(row)
