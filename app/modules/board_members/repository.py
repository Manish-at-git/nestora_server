"""SQL access for board memberships and association directories."""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Account
from app.modules.board_members.models import BoardMember


class BoardMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def association_ids_for_admin(self, account_id: str) -> list[str]:
        result = await self.session.scalars(
            text("SELECT association_id FROM admin_associations WHERE admin_id=:account_id"),
            {"account_id": account_id},
        )
        return list(result.all())

    async def association_exists(self, association_id: str) -> bool:
        return bool(
            await self.session.scalar(
                text("SELECT id FROM associations WHERE id=:id AND is_deleted=0 LIMIT 1"),
                {"id": association_id},
            )
        )

    async def member_association_id(self, account: Account) -> str | None:
        active = await self.session.scalar(
            text("SELECT association_id FROM board_members WHERE account_id=:account_id AND status='active' AND is_deleted=0 ORDER BY created_at DESC LIMIT 1"),
            {"account_id": account.id},
        )
        if active:
            return active
        if not account.user_id:
            return None
        return await self.session.scalar(
            text(
                "SELECT COALESCE(ud.association_id,b.association_id) FROM user_details ud "
                "LEFT JOIN units u ON u.id=ud.unit_id LEFT JOIN blocks b ON b.id=u.block_id "
                "WHERE ud.user_id=:user_id AND ud.is_deleted=0 LIMIT 1"
            ),
            {"user_id": account.user_id},
        )

    async def account_belongs_to_association(self, account_id: str, association_id: str) -> bool:
        return bool(
            await self.session.scalar(
                text(
                    "SELECT a.account_id FROM accounts a "
                    "JOIN user_details ud ON ud.user_id=a.user_id "
                    "LEFT JOIN units u ON u.id=ud.unit_id LEFT JOIN blocks b ON b.id=u.block_id "
                    "WHERE a.account_id=:account_id AND COALESCE(ud.association_id,b.association_id)=:association_id "
                    "AND ud.is_deleted=0 LIMIT 1"
                ),
                {"account_id": account_id, "association_id": association_id},
            )
        )

    async def account_role_code(self, account_id: str) -> str | None:
        return await self.session.scalar(
            text("SELECT r.code FROM accounts a JOIN roles r ON r.id=a.role_id WHERE a.account_id=:account_id AND r.is_deleted=0"),
            {"account_id": account_id},
        )

    async def role_id(self, role_code: str) -> str | None:
        return await self.session.scalar(
            text("SELECT id FROM roles WHERE code=:code AND is_deleted=0 LIMIT 1"),
            {"code": role_code},
        )

    async def active_membership(self, account_id: str, association_id: str) -> BoardMember | None:
        return await self.session.scalar(
            select(BoardMember).where(
                BoardMember.account_id == account_id,
                BoardMember.association_id == association_id,
                BoardMember.status == "active",
                BoardMember.is_deleted.is_(False),
            )
        )

    async def list_members(self, association_id: str | None = None) -> list[dict]:
        query = (
            "SELECT bm.id,bm.association_id,bm.account_id,bm.term_start_date,bm.term_end_date,bm.status,bm.created_at,"
            "a.user_id,a.email,COALESCE(ud.name,a.email) name,ud.contact_number,ud.profile_pic_url,"
            "ud.board_member_since,assoc.name association_name,r.code role "
            "FROM board_members bm JOIN accounts a ON a.account_id=bm.account_id "
            "LEFT JOIN user_details ud ON ud.user_id=a.user_id JOIN associations assoc ON assoc.id=bm.association_id "
            "LEFT JOIN roles r ON r.id=a.role_id WHERE bm.is_deleted=0 AND assoc.is_deleted=0"
        )
        params: dict = {}
        if association_id:
            query += " AND bm.association_id=:association_id"
            params["association_id"] = association_id
        query += " ORDER BY bm.created_at DESC"
        result = await self.session.execute(text(query), params)
        return [dict(row) for row in result.mappings().all()]

    async def directory(self, association_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT bm.account_id,a.user_id,COALESCE(ud.name,a.email) name,a.email,ud.contact_number,"
                "ud.profile_pic_url,ud.board_member_since,bm.term_start_date,bm.term_end_date "
                "FROM board_members bm JOIN accounts a ON a.account_id=bm.account_id "
                "LEFT JOIN user_details ud ON ud.user_id=a.user_id "
                "WHERE bm.association_id=:association_id AND bm.status='active' AND bm.is_deleted=0 "
                "AND (bm.term_end_date IS NULL OR bm.term_end_date >= CURRENT_DATE) ORDER BY name ASC"
            ),
            {"association_id": association_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def homeowners(self, association_id: str, homeowner_code: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT a.account_id,a.user_id,COALESCE(ud.name,a.email) name,a.email,ud.profile_pic_url "
                "FROM accounts a JOIN roles r ON r.id=a.role_id JOIN user_details ud ON ud.user_id=a.user_id "
                "LEFT JOIN units u ON u.id=ud.unit_id LEFT JOIN blocks b ON b.id=u.block_id "
                "WHERE COALESCE(ud.association_id,b.association_id)=:association_id AND r.code=:role_code "
                "AND ud.is_deleted=0 ORDER BY name ASC"
            ),
            {"association_id": association_id, "role_code": homeowner_code},
        )
        return [dict(row) for row in result.mappings().all()]

    def add(self, membership: BoardMember) -> None:
        self.session.add(membership)
