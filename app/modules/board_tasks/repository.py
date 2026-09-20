"""Database access for board tasks, members, messages, and notifications."""

import uuid
from collections.abc import Iterable

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AccountStatus, RoleCode
from app.modules.auth.models import Account
from app.modules.board_tasks.models import BoardTask, BoardTaskMessage


class BoardTaskRepository:
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
                "SELECT b.association_id FROM user_details ud "
                "JOIN units u ON u.id = ud.unit_id JOIN blocks b ON b.id = u.block_id "
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

    async def board_member(self, account_id: str, association_id: str) -> bool:
        return bool(
            await self.session.scalar(
                text(
                    "SELECT ac.account_id FROM accounts ac JOIN roles r ON r.id = ac.role_id "
                    "JOIN user_details ud ON ud.user_id = ac.user_id "
                    "JOIN units u ON u.id = ud.unit_id JOIN blocks b ON b.id = u.block_id "
                    "WHERE ac.account_id = :account_id AND ac.status = :account_status "
                    "AND r.code = :role_code AND r.is_active = 1 AND r.is_deleted = 0 "
                    "AND ud.is_deleted = 0 AND b.association_id = :association_id LIMIT 1"
                ),
                {
                    "account_id": account_id,
                    "account_status": AccountStatus.ACTIVE,
                    "role_code": RoleCode.BOARD_MEMBER,
                    "association_id": association_id,
                },
            )
        )

    async def board_members(self, association_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT ac.account_id, COALESCE(ud.name, ac.email) AS name, ac.email, "
                "ud.contact_number, ud.profile_pic_url, ud.board_member_since "
                "FROM accounts ac JOIN roles r ON r.id = ac.role_id "
                "JOIN user_details ud ON ud.user_id = ac.user_id "
                "JOIN units u ON u.id = ud.unit_id JOIN blocks b ON b.id = u.block_id "
                "WHERE ac.status = :account_status AND r.code = :role_code "
                "AND r.is_active = 1 AND r.is_deleted = 0 AND ud.is_deleted = 0 "
                "AND b.association_id = :association_id ORDER BY ud.name, ac.email"
            ),
            {
                "account_status": AccountStatus.ACTIVE,
                "role_code": RoleCode.BOARD_MEMBER,
                "association_id": association_id,
            },
        )
        return [dict(row) for row in result.mappings().all()]

    async def list(self, association_ids: Iterable[str] | None = None) -> list[dict]:
        query = (
            "SELECT bt.id, bt.association_id, bt.created_by, bt.title, bt.description, "
            "bt.supervised_by, bt.image_url, bt.status, bt.created_at, bt.updated_at, "
            "a.name AS association_name, "
            "COALESCE(sud.name, se.name, sac.email) AS supervised_by_name, "
            "COALESCE(cud.name, ce.name, cac.email) AS created_by_name "
            "FROM board_tasks bt JOIN associations a ON a.id = bt.association_id "
            "LEFT JOIN accounts sac ON sac.account_id = bt.supervised_by "
            "LEFT JOIN user_details sud ON sud.user_id = sac.user_id "
            "LEFT JOIN employees se ON se.employee_id = sac.employee_id "
            "LEFT JOIN accounts cac ON cac.account_id = bt.created_by "
            "LEFT JOIN user_details cud ON cud.user_id = cac.user_id "
            "LEFT JOIN employees ce ON ce.employee_id = cac.employee_id "
            "WHERE bt.is_deleted = 0 AND a.is_deleted = 0"
        )
        params: dict = {}
        if association_ids is not None:
            ids = tuple(dict.fromkeys(association_ids))
            if not ids:
                return []
            query += " AND bt.association_id IN :association_ids"
            params["association_ids"] = ids
        statement = text(query + " ORDER BY bt.created_at DESC")
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        return [dict(row) for row in result.mappings().all()]

    async def get(self, task_id: str) -> dict | None:
        result = await self.session.execute(
            text(
                "SELECT bt.id, bt.association_id, bt.created_by, bt.title, bt.description, "
                "bt.supervised_by, bt.image_url, bt.status, bt.created_at, bt.updated_at, "
                "a.name AS association_name, COALESCE(sud.name, se.name, sac.email) AS supervised_by_name, "
                "COALESCE(cud.name, ce.name, cac.email) AS created_by_name "
                "FROM board_tasks bt JOIN associations a ON a.id = bt.association_id "
                "LEFT JOIN accounts sac ON sac.account_id = bt.supervised_by "
                "LEFT JOIN user_details sud ON sud.user_id = sac.user_id "
                "LEFT JOIN employees se ON se.employee_id = sac.employee_id "
                "LEFT JOIN accounts cac ON cac.account_id = bt.created_by "
                "LEFT JOIN user_details cud ON cud.user_id = cac.user_id "
                "LEFT JOIN employees ce ON ce.employee_id = cac.employee_id "
                "WHERE bt.id = :task_id AND bt.is_deleted = 0 AND a.is_deleted = 0 LIMIT 1"
            ),
            {"task_id": task_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def task_model(self, task_id: str) -> BoardTask | None:
        return await self.session.scalar(
            select(BoardTask).where(BoardTask.id == task_id, BoardTask.is_deleted.is_(False))
        )

    async def messages(self, task_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT m.id, m.board_task_id, m.sender_id, m.message, m.attachment_url, "
                "m.created_at, a.email, a.role_id, "
                "COALESCE(ud.name, e.name, a.email) AS sender_name "
                "FROM board_task_messages m JOIN accounts a ON a.account_id = m.sender_id "
                "LEFT JOIN user_details ud ON ud.user_id = a.user_id "
                "LEFT JOIN employees e ON e.employee_id = a.employee_id "
                "WHERE m.board_task_id = :task_id AND m.is_deleted = 0 ORDER BY m.created_at"
            ),
            {"task_id": task_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def message_event(self, message_id: str) -> dict | None:
        result = await self.session.execute(
            text(
                "SELECT m.id, m.board_task_id, m.sender_id, m.message, m.attachment_url, "
                "m.created_at, a.email, a.role_id, "
                "COALESCE(ud.name, e.name, a.email) AS sender_name "
                "FROM board_task_messages m JOIN accounts a ON a.account_id = m.sender_id "
                "LEFT JOIN user_details ud ON ud.user_id = a.user_id "
                "LEFT JOIN employees e ON e.employee_id = a.employee_id "
                "WHERE m.id = :message_id AND m.is_deleted = 0 LIMIT 1"
            ),
            {"message_id": message_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def participant_account_ids(self, task: BoardTask) -> set[str]:
        ids = {task.created_by, task.supervised_by}
        result = await self.session.scalars(
            text(
                "SELECT ac.account_id FROM accounts ac JOIN roles r ON r.id = ac.role_id "
                "JOIN user_details ud ON ud.user_id = ac.user_id "
                "JOIN units u ON u.id = ud.unit_id JOIN blocks b ON b.id = u.block_id "
                "WHERE ac.status = :account_status AND r.code = :role_code "
                "AND r.is_active = 1 AND r.is_deleted = 0 AND ud.is_deleted = 0 "
                "AND b.association_id = :association_id"
            ),
            {
                "account_status": AccountStatus.ACTIVE,
                "role_code": RoleCode.BOARD_MEMBER,
                "association_id": task.association_id,
            },
        )
        ids.update(result.all())
        admins = await self.session.scalars(
            text("SELECT admin_id FROM admin_associations WHERE association_id = :association_id"),
            {"association_id": task.association_id},
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

    def add(self, task: BoardTask) -> None:
        self.session.add(task)

    def add_message(self, message: BoardTaskMessage) -> None:
        self.session.add(message)
