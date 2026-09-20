"""SQL access for announcements, reactions, and comments."""

from collections.abc import Iterable

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.announcements.models import Announcement, AnnouncementComment, AnnouncementLike
from app.modules.auth.models import Account


class AnnouncementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def association_ids_for_admin(self, account_id: str) -> list[str]:
        result = await self.session.scalars(
            text("SELECT association_id FROM admin_associations WHERE admin_id = :account_id"),
            {"account_id": account_id},
        )
        return list(result.all())

    async def member_association_id(self, account: Account) -> str | None:
        if not account.user_id:
            return None
        return await self.session.scalar(
            text(
                "SELECT COALESCE(ud.association_id, b.association_id) FROM user_details ud "
                "LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
                "WHERE ud.user_id = :user_id AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"user_id": account.user_id},
        )

    async def association_exists(self, association_id: str) -> bool:
        return bool(
            await self.session.scalar(
                text("SELECT id FROM associations WHERE id = :id AND is_deleted = 0 LIMIT 1"),
                {"id": association_id},
            )
        )

    async def list(
        self,
        association_ids: Iterable[str] | None,
        account_id: str,
        audiences: Iterable[str] | None = None,
    ) -> list[dict]:
        query = (
            "SELECT a.id, a.title, a.body, a.category, a.pinned, a.created_at, a.updated_at, "
            "a.association_id, a.audience, a.attachment_url, "
            "COALESCE(ud.name, ac.email) AS author_name, r.code AS author_role, "
            "(SELECT COUNT(*) FROM announcement_likes al WHERE al.announcement_id = a.id AND al.is_deleted = 0) AS likes_count, "
            "(SELECT COUNT(*) FROM announcement_comments acm WHERE acm.announcement_id = a.id AND acm.is_deleted = 0) AS comments_count, "
            "EXISTS(SELECT 1 FROM announcement_likes mine WHERE mine.announcement_id = a.id "
            "AND mine.account_id = :account_id AND mine.is_deleted = 0) AS liked "
            "FROM announcements a LEFT JOIN accounts ac ON ac.account_id = a.created_by "
            "LEFT JOIN user_details ud ON ud.user_id = ac.user_id "
            "LEFT JOIN roles r ON r.id = ac.role_id "
            "WHERE a.is_deleted = 0"
        )
        params: dict = {"account_id": account_id}
        if association_ids is not None:
            ids = tuple(dict.fromkeys(association_ids))
            if not ids:
                return []
            query += " AND a.association_id IN :association_ids"
            params["association_ids"] = ids
        if audiences is not None:
            audience_values = tuple(dict.fromkeys(audiences))
            if not audience_values:
                return []
            query += " AND a.audience IN :audiences"
            params["audiences"] = audience_values
        statement = text(query + " ORDER BY a.pinned DESC, a.created_at DESC")
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        if audiences is not None:
            statement = statement.bindparams(bindparam("audiences", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def announcement_model(self, announcement_id: str) -> Announcement | None:
        return await self.session.scalar(
            select(Announcement).where(
                Announcement.id == announcement_id,
                Announcement.is_deleted.is_(False),
            )
        )

    async def like(self, announcement_id: str, account_id: str, include_deleted: bool = False) -> AnnouncementLike | None:
        statement = select(AnnouncementLike).where(
            AnnouncementLike.announcement_id == announcement_id,
            AnnouncementLike.account_id == account_id,
        )
        if not include_deleted:
            statement = statement.where(AnnouncementLike.is_deleted.is_(False))
        return await self.session.scalar(statement)

    async def comments(self, announcement_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT c.id, c.comment, c.created_at, COALESCE(ud.name, ac.email) AS author_name "
                "FROM announcement_comments c JOIN accounts ac ON c.account_id = ac.account_id "
                "LEFT JOIN user_details ud ON ac.user_id = ud.user_id "
                "WHERE c.announcement_id = :announcement_id AND c.is_deleted = 0 "
                "ORDER BY c.created_at ASC"
            ),
            {"announcement_id": announcement_id},
        )
        return [dict(row) for row in result.mappings().all()]

    def add_announcement(self, announcement: Announcement) -> None:
        self.session.add(announcement)

    def add_like(self, like: AnnouncementLike) -> None:
        self.session.add(like)

    def add_comment(self, comment: AnnouncementComment) -> None:
        self.session.add(comment)
