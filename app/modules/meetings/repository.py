"""Database access for meetings, attendance, audience members, and notifications."""

import uuid
from collections.abc import Iterable
from datetime import datetime, time, timedelta

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AccountStatus, RoleCode
from app.modules.auth.models import Account
from app.modules.meetings.models import Meeting, MeetingAttendance
from app.modules.notifications.service import notify_association_audience


class MeetingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def association_ids_for_admin(self, account_id: str) -> list[str]:
        result = await self.session.scalars(
            text("SELECT association_id FROM admin_associations WHERE admin_id = :account_id"),
            {"account_id": account_id},
        )
        return list(result.all())

    async def member_context(self, account: Account) -> dict | None:
        if not account.user_id:
            return None
        result = await self.session.execute(
            text(
                "SELECT b.association_id, b.id AS block_id FROM user_details ud "
                "JOIN units u ON u.id = ud.unit_id JOIN blocks b ON b.id = u.block_id "
                "WHERE ud.user_id = :user_id AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"user_id": account.user_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def association_exists(self, association_id: str) -> bool:
        return bool(await self.session.scalar(text("SELECT id FROM associations WHERE id = :id AND is_deleted = 0 LIMIT 1"), {"id": association_id}))

    async def block_belongs_to_association(self, block_id: str, association_id: str) -> bool:
        return bool(await self.session.scalar(text("SELECT id FROM blocks WHERE id = :id AND association_id = :association_id LIMIT 1"), {"id": block_id, "association_id": association_id}))

    async def organizer_belongs_to_association(self, account_id: str, association_id: str) -> bool:
        result = await self.session.scalar(
            text(
                "SELECT ac.account_id FROM accounts ac JOIN roles r ON r.id = ac.role_id "
                "LEFT JOIN user_details ud ON ud.user_id = ac.user_id "
                "LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
                "WHERE ac.account_id = :account_id AND ac.status = :account_status "
                "AND r.is_active = 1 AND r.is_deleted = 0 AND ("
                "(r.code = :board_role AND ud.is_deleted = 0 AND b.association_id = :association_id) "
                "OR (r.code = :admin_role AND EXISTS (SELECT 1 FROM admin_associations aa "
                "WHERE aa.admin_id = ac.account_id AND aa.association_id = :association_id)) "
                "OR r.code = :super_admin_role) LIMIT 1"
            ),
            {
                "account_id": account_id,
                "account_status": AccountStatus.ACTIVE,
                "board_role": RoleCode.BOARD_MEMBER,
                "admin_role": RoleCode.ADMIN,
                "super_admin_role": RoleCode.SUPER_ADMIN,
                "association_id": association_id,
            },
        )
        return bool(result)

    async def organizers(self, association_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT ac.account_id, COALESCE(ud.name, ac.email) AS name, ac.email "
                "FROM accounts ac JOIN roles r ON r.id = ac.role_id "
                "LEFT JOIN user_details ud ON ud.user_id = ac.user_id "
                "LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
                "WHERE ac.status = :account_status AND r.is_active = 1 AND r.is_deleted = 0 AND ("
                "(r.code = :board_role AND ud.is_deleted = 0 AND b.association_id = :association_id) "
                "OR (r.code = :admin_role AND EXISTS (SELECT 1 FROM admin_associations aa "
                "WHERE aa.admin_id = ac.account_id AND aa.association_id = :association_id)) "
                "OR r.code = :super_admin_role) "
                "ORDER BY ud.name, ac.email"
            ),
            {
                "account_status": AccountStatus.ACTIVE,
                "board_role": RoleCode.BOARD_MEMBER,
                "admin_role": RoleCode.ADMIN,
                "super_admin_role": RoleCode.SUPER_ADMIN,
                "association_id": association_id,
            },
        )
        return [dict(row) for row in result.mappings().all()]

    async def blocks(self, association_id: str) -> list[dict]:
        result = await self.session.execute(text("SELECT id, name FROM blocks WHERE association_id = :association_id ORDER BY name"), {"association_id": association_id})
        return [dict(row) for row in result.mappings().all()]

    async def list(
        self,
        account_id: str,
        association_ids: Iterable[str] | None,
        audience: str | None = None,
        block_id: str | None = None,
    ) -> list[dict]:
        query = (
            "SELECT m.id, m.association_id, a.name AS association_name, m.created_by, "
            "COALESCE(cud.name, ce.name, cac.email) AS created_by_name, m.title, m.meeting_type, "
            "m.priority, m.audience, m.agenda, m.description, m.meeting_date, m.meeting_time, "
            "m.duration, m.venue, m.meeting_link, m.organizer, "
            "COALESCE(oud.name, oe.name, oac.email) AS organizer_name, m.attachment_url, "
            "m.target_block_id, b.name AS target_block_name, m.status, m.meeting_minutes, "
            "m.discussed_topic, m.created_at, m.updated_at, "
            "(SELECT ma.status FROM meeting_attendance ma WHERE ma.meeting_id = m.id "
            "AND ma.account_id = :account_id AND ma.is_deleted = 0 LIMIT 1) AS my_attendance_status, "
            "(SELECT COUNT(*) FROM meeting_attendance ma WHERE ma.meeting_id = m.id AND ma.status = 'Yes' AND ma.is_deleted = 0) AS yes_count, "
            "(SELECT COUNT(*) FROM meeting_attendance ma WHERE ma.meeting_id = m.id AND ma.status = 'No' AND ma.is_deleted = 0) AS no_count, "
            "(SELECT COUNT(*) FROM meeting_attendance ma WHERE ma.meeting_id = m.id AND ma.status = 'Maybe' AND ma.is_deleted = 0) AS maybe_count "
            "FROM meetings m JOIN associations a ON a.id = m.association_id "
            "LEFT JOIN blocks b ON b.id = m.target_block_id "
            "LEFT JOIN accounts oac ON oac.account_id = m.organizer LEFT JOIN user_details oud ON oud.user_id = oac.user_id "
            "LEFT JOIN employees oe ON oe.employee_id = oac.employee_id "
            "LEFT JOIN accounts cac ON cac.account_id = m.created_by LEFT JOIN user_details cud ON cud.user_id = cac.user_id "
            "LEFT JOIN employees ce ON ce.employee_id = cac.employee_id "
            "WHERE m.is_deleted = 0 AND a.is_deleted = 0"
        )
        params: dict = {"account_id": account_id}
        if association_ids is not None:
            ids = tuple(dict.fromkeys(association_ids))
            if not ids:
                return []
            query += " AND m.association_id IN :association_ids"
            params["association_ids"] = ids
        if audience:
            query += " AND m.audience = :audience"
            params["audience"] = audience
            if block_id:
                query += " AND (m.target_block_id IS NULL OR m.target_block_id = '' OR m.target_block_id = :block_id)"
                params["block_id"] = block_id
        statement = text(query + " ORDER BY m.created_at DESC")
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        result = await self.session.execute(statement, params)
        rows = []
        for row in result.mappings().all():
            item = dict(row)
            if isinstance(item.get("meeting_time"), timedelta):
                total_seconds = int(item["meeting_time"].total_seconds()) % (24 * 60 * 60)
                item["meeting_time"] = time(total_seconds // 3600, (total_seconds % 3600) // 60, total_seconds % 60)
            eligible = await self._eligible_count(item["association_id"])
            item["no_response_count"] = max(0, eligible - item["yes_count"] - item["no_count"] - item["maybe_count"])
            item["attendance_stats"] = {
                "yes_count": item.pop("yes_count"),
                "no_count": item.pop("no_count"),
                "maybe_count": item.pop("maybe_count"),
                "no_response_count": item.pop("no_response_count"),
            }
            rows.append(item)
        return rows

    async def _eligible_count(self, association_id: str) -> int:
        return int(await self.session.scalar(text(
            "SELECT COUNT(DISTINCT ac.account_id) FROM accounts ac JOIN roles r ON r.id = ac.role_id "
            "JOIN user_details ud ON ud.user_id = ac.user_id JOIN units u ON u.id = ud.unit_id "
            "JOIN blocks b ON b.id = u.block_id WHERE ac.status = :account_status "
            "AND r.code IN :role_codes AND r.is_active = 1 AND r.is_deleted = 0 AND ud.is_deleted = 0 "
            "AND b.association_id = :association_id"
        ).bindparams(bindparam("role_codes", expanding=True)), {
            "account_status": AccountStatus.ACTIVE,
            "role_codes": (
                RoleCode.HOMEOWNER,
                RoleCode.TENANT,
                RoleCode.BOARD_MEMBER,
                RoleCode.COMMITTEE_MEMBER,
            ),
            "association_id": association_id,
        }) or 0)

    async def get(self, meeting_id: str) -> Meeting | None:
        return await self.session.scalar(select(Meeting).where(Meeting.id == meeting_id, Meeting.is_deleted.is_(False)))

    async def attendance(self, meeting_id: str, account_id: str) -> MeetingAttendance | None:
        return await self.session.scalar(select(MeetingAttendance).where(MeetingAttendance.meeting_id == meeting_id, MeetingAttendance.account_id == account_id, MeetingAttendance.is_deleted.is_(False)))

    async def notify_audience(
        self,
        association_id: str,
        audience: str,
        block_id: str | None,
        title: str,
        message: str,
        sender_id: str,
        meeting_id: str,
    ) -> None:
        await notify_association_audience(
            self.session,
            association_id,
            audience,
            title,
            message,
            sender_id,
            block_id,
            notification_type="meeting",
            entity_type="meeting",
            entity_id=meeting_id,
            action_url="/meetings",
        )

    def add(self, meeting: Meeting) -> None:
        self.session.add(meeting)

    def add_attendance(self, attendance: MeetingAttendance) -> None:
        self.session.add(attendance)
