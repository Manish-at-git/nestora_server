"""SQL access for committee definitions, memberships, and role transitions."""

import uuid
from collections.abc import Iterable

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AccountStatus, RoleCode
from app.modules.auth.models import Account
from app.modules.committees.models import BoardCommitteeChatMessage, Committee, CommitteeMember


class CommitteeRepository:
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
                "SELECT COALESCE(ud.association_id, b.association_id) "
                "FROM user_details ud LEFT JOIN units u ON u.id = ud.unit_id "
                "LEFT JOIN blocks b ON b.id = u.block_id "
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

    async def list_homeowners(self, association_ids: Iterable[str] | None) -> list[dict]:
        query = (
            "SELECT ac.account_id, ud.user_id, ud.name, ac.email, ud.profile_pic_url, "
            "ud.contact_number, u.unit_number, b.name AS block_name, "
            "b.association_id, assoc.name AS association_name "
            "FROM accounts ac JOIN roles r ON r.id = ac.role_id "
            "JOIN user_details ud ON ud.user_id = ac.user_id "
            "LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
            "JOIN associations assoc ON assoc.id = COALESCE(ud.association_id, b.association_id) "
            "WHERE ac.status = :account_status AND r.code = :role_code "
            "AND r.is_active = 1 AND r.is_deleted = 0 AND ud.is_deleted = 0 AND assoc.is_deleted = 0"
        )
        params: dict = {"account_status": AccountStatus.ACTIVE, "role_code": RoleCode.HOMEOWNER}
        if association_ids is not None:
            ids = tuple(dict.fromkeys(association_ids))
            if not ids:
                return []
            query += " AND assoc.id IN :association_ids"
            params["association_ids"] = ids
        statement = text(query + " ORDER BY assoc.name, b.name, u.unit_number, ud.name").bindparams(
            bindparam("association_ids", expanding=True)
        ) if association_ids is not None else text(query + " ORDER BY assoc.name, b.name, u.unit_number, ud.name")
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def homeowner_in_association(self, user_id: str, association_id: str) -> bool:
        return bool(
            await self.session.scalar(
                text(
                    "SELECT ac.account_id FROM accounts ac JOIN roles r ON r.id = ac.role_id "
                    "JOIN user_details ud ON ud.user_id = ac.user_id "
                    "LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
                    "WHERE ud.user_id = :user_id AND ac.status = :account_status "
                    "AND r.code = :role_code AND r.is_active = 1 AND r.is_deleted = 0 "
                    "AND ud.is_deleted = 0 AND COALESCE(ud.association_id, b.association_id) = :association_id LIMIT 1"
                ),
                {
                    "user_id": user_id,
                    "account_status": AccountStatus.ACTIVE,
                    "role_code": RoleCode.HOMEOWNER,
                    "association_id": association_id,
                },
            )
        )

    async def list_committees(self, association_ids: Iterable[str] | None) -> list[dict]:
        query = (
            "SELECT c.id, c.association_id, c.name, c.description, c.start_date, c.end_date, c.created_at, "
            "a.name AS association_name, "
            "(SELECT COUNT(*) FROM committee_members cm WHERE cm.committee_id = c.id AND cm.is_deleted = 0) AS member_count "
            "FROM committees c JOIN associations a ON a.id = c.association_id "
            "WHERE c.is_deleted = 0 AND a.is_deleted = 0"
        )
        params: dict = {}
        if association_ids is not None:
            ids = tuple(dict.fromkeys(association_ids))
            if not ids:
                return []
            query += " AND c.association_id IN :association_ids"
            params["association_ids"] = ids
        statement = text(query + " ORDER BY c.created_at DESC")
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        rows = [dict(row) for row in result.mappings().all()]
        if not rows:
            return rows
        committee_ids = tuple(row["id"] for row in rows)
        members_result = await self.session.execute(
            text(
                "SELECT cm.id, cm.committee_id, cm.user_id, cm.start_date, cm.end_date, "
                "ud.name, ud.profile_pic_url, ac.email "
                "FROM committee_members cm JOIN user_details ud ON ud.user_id = cm.user_id "
                "JOIN accounts ac ON ac.user_id = cm.user_id "
                "WHERE cm.committee_id IN :committee_ids AND cm.is_deleted = 0 AND ud.is_deleted = 0 "
                "ORDER BY ud.name, ac.email"
            ).bindparams(bindparam("committee_ids", expanding=True)),
            {"committee_ids": committee_ids},
        )
        grouped: dict[str, list[dict]] = {row["id"]: [] for row in rows}
        for member in members_result.mappings().all():
            item = dict(member)
            grouped[item["committee_id"]].append(item)
        for row in rows:
            row["members"] = grouped[row["id"]]
        return rows

    async def committee_model(self, committee_id: str) -> Committee | None:
        return await self.session.scalar(
            select(Committee).where(Committee.id == committee_id, Committee.is_deleted.is_(False))
        )

    async def committee_member(self, committee_id: str, user_id: str, include_deleted: bool = False) -> CommitteeMember | None:
        statement = select(CommitteeMember).where(
            CommitteeMember.committee_id == committee_id, CommitteeMember.user_id == user_id
        )
        if not include_deleted:
            statement = statement.where(CommitteeMember.is_deleted.is_(False))
        return await self.session.scalar(statement.order_by(CommitteeMember.created_at.desc()))

    async def member_model(self, member_id: str) -> CommitteeMember | None:
        return await self.session.scalar(
            select(CommitteeMember).where(
                CommitteeMember.id == member_id, CommitteeMember.is_deleted.is_(False)
            )
        )

    async def list_members(self, association_ids: Iterable[str] | None) -> list[dict]:
        query = (
            "SELECT cm.id AS committee_member_id, cm.committee_id, cm.user_id, "
            "cm.start_date AS role_start_date, cm.end_date AS role_end_date, cm.created_at, "
            "c.name AS committee_name, c.association_id, assoc.name AS association_name, "
            "ud.name, ac.email, ud.contact_number AS phone, ud.profile_pic_url "
            "FROM committee_members cm JOIN committees c ON cm.committee_id = c.id "
            "JOIN associations assoc ON c.association_id = assoc.id "
            "JOIN accounts ac ON cm.user_id = ac.user_id JOIN user_details ud ON cm.user_id = ud.user_id "
            "WHERE cm.is_deleted = 0 AND c.is_deleted = 0 AND assoc.is_deleted = 0 AND ud.is_deleted = 0"
        )
        params: dict = {}
        if association_ids is not None:
            ids = tuple(dict.fromkeys(association_ids))
            if not ids:
                return []
            query += " AND c.association_id IN :association_ids"
            params["association_ids"] = ids
        statement = text(query + " ORDER BY c.name, ud.name")
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def user_committees(self, user_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT c.id, c.association_id, c.name, c.description, c.start_date, c.end_date, c.created_at, "
                "a.name AS association_name, cm.id AS committee_member_id, cm.start_date AS role_start_date, "
                "cm.end_date AS role_end_date "
                "FROM committee_members cm JOIN committees c ON c.id = cm.committee_id "
                "JOIN associations a ON a.id = c.association_id "
                "WHERE cm.user_id = :user_id AND cm.is_deleted = 0 AND c.is_deleted = 0 AND a.is_deleted = 0 "
                "ORDER BY c.created_at DESC"
            ),
            {"user_id": user_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def chat_messages(self, pool_type: str, pool_id: str, association_id: str, account_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT c.id, c.association_id, c.pool_type, c.pool_id, c.sender_id, c.message, "
                "c.attachment_url, c.created_at, ac.email, "
                "COALESCE(ud.name, e.name, ac.email) AS sender_name, ud.profile_pic_url, "
                "(c.sender_id = :account_id) AS is_mine "
                "FROM board_committee_chat c JOIN accounts ac ON ac.account_id = c.sender_id "
                "LEFT JOIN user_details ud ON ud.user_id = ac.user_id "
                "LEFT JOIN employees e ON e.employee_id = ac.employee_id "
                "WHERE c.association_id = :association_id AND c.pool_type = :pool_type "
                "AND c.pool_id = :pool_id AND c.is_deleted = 0 ORDER BY c.created_at"
            ),
            {"account_id": account_id, "association_id": association_id, "pool_type": pool_type, "pool_id": pool_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def chat_message(self, message_id: str) -> dict | None:
        result = await self.session.execute(
            text(
                "SELECT c.id, c.association_id, c.pool_type, c.pool_id, c.sender_id, c.message, "
                "c.attachment_url, c.created_at, ac.email, "
                "COALESCE(ud.name, e.name, ac.email) AS sender_name, ud.profile_pic_url "
                "FROM board_committee_chat c JOIN accounts ac ON ac.account_id = c.sender_id "
                "LEFT JOIN user_details ud ON ud.user_id = ac.user_id "
                "LEFT JOIN employees e ON e.employee_id = ac.employee_id "
                "WHERE c.id = :message_id AND c.is_deleted = 0 LIMIT 1"
            ),
            {"message_id": message_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def chat_participants(self, pool_type: str, pool_id: str, association_id: str) -> set[str]:
        result = await self.session.scalars(
            text(
                "SELECT DISTINCT ac.account_id FROM accounts ac JOIN roles r ON r.id = ac.role_id "
                "JOIN user_details ud ON ud.user_id = ac.user_id "
                "LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
                "WHERE ac.status = :account_status AND r.is_active = 1 AND r.is_deleted = 0 "
                "AND ud.is_deleted = 0 AND COALESCE(ud.association_id, b.association_id) = :association_id "
                "AND r.code IN :role_codes"
                + (" AND EXISTS (SELECT 1 FROM committee_members cm WHERE cm.user_id = ac.user_id AND cm.committee_id = :pool_id AND cm.is_deleted = 0)" if pool_type == "committee" else "")
            ).bindparams(bindparam("role_codes", expanding=True)),
            {
                "account_status": AccountStatus.ACTIVE,
                "association_id": association_id,
                "role_codes": (RoleCode.ADMIN, RoleCode.BOARD_MEMBER, RoleCode.COMMITTEE_MEMBER),
                "pool_id": pool_id,
            },
        )
        ids = set(result.all())
        admins = await self.session.scalars(
            text("SELECT admin_id FROM admin_associations WHERE association_id = :association_id"),
            {"association_id": association_id},
        )
        ids.update(admins.all())
        super_admins = await self.session.scalars(
            text(
                "SELECT ac.account_id FROM accounts ac JOIN roles r ON r.id = ac.role_id "
                "WHERE ac.status = :account_status AND r.code = :role_code "
                "AND r.is_active = 1 AND r.is_deleted = 0"
            ),
            {"account_status": AccountStatus.ACTIVE, "role_code": RoleCode.SUPER_ADMIN},
        )
        ids.update(super_admins.all())
        return ids

    def add_chat_message(self, message: BoardCommitteeChatMessage) -> None:
        self.session.add(message)

    async def set_account_role(self, user_id: str, role_code: RoleCode) -> None:
        role_id = await self.session.scalar(
            text("SELECT id FROM roles WHERE code = :role_code AND is_active = 1 AND is_deleted = 0 LIMIT 1"),
            {"role_code": role_code},
        )
        if role_id:
            await self.session.execute(
                text("UPDATE accounts SET role_id = :role_id WHERE user_id = :user_id"),
                {"role_id": role_id, "user_id": user_id},
            )

    async def restore_homeowner_role(self, user_id: str) -> None:
        homeowner_role_id = await self.session.scalar(
            text("SELECT id FROM roles WHERE code = :role_code AND is_active = 1 AND is_deleted = 0 LIMIT 1"),
            {"role_code": RoleCode.HOMEOWNER},
        )
        if homeowner_role_id:
            await self.session.execute(
                text(
                    "UPDATE accounts ac JOIN roles current_role ON current_role.id = ac.role_id "
                    "SET ac.role_id = :homeowner_role_id WHERE ac.user_id = :user_id "
                    "AND current_role.code = :committee_role_code"
                ),
                {
                    "homeowner_role_id": homeowner_role_id,
                    "user_id": user_id,
                    "committee_role_code": RoleCode.COMMITTEE_MEMBER,
                },
            )

    async def has_active_membership(self, user_id: str) -> bool:
        return bool(
            await self.session.scalar(
                text(
                    "SELECT cm.id FROM committee_members cm JOIN committees c ON c.id = cm.committee_id "
                    "WHERE cm.user_id = :user_id AND cm.is_deleted = 0 AND c.is_deleted = 0 LIMIT 1"
                ),
                {"user_id": user_id},
            )
        )

    def add_committee(self, committee: Committee) -> None:
        self.session.add(committee)

    def add_member(self, member: CommitteeMember) -> None:
        self.session.add(member)
