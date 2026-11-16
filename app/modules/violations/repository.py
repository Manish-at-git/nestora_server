"""SQL access for association-scoped violations."""

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AccountStatus, RoleCode
from app.modules.notifications.service import create_notification, notify_accounts
from app.modules.violations.models import Violation, ViolationThreadMessage


class ViolationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, violation_id: str) -> Violation | None:
        return await self.session.get(Violation, violation_id)

    async def next_sequence(self, association_id: str) -> int:
        """Allocate an association-scoped number while the transaction owns its row lock."""
        await self.session.execute(
            text(
                "INSERT INTO violation_sequences (association_id, next_number) VALUES (:association_id, 1) "
                "ON DUPLICATE KEY UPDATE next_number = next_number + 1"
            ),
            {"association_id": association_id},
        )
        return int(
            await self.session.scalar(
                text("SELECT next_number FROM violation_sequences WHERE association_id = :association_id FOR UPDATE"),
                {"association_id": association_id},
            )
        )

    async def resident_context(self, account_id: str) -> dict | None:
        result = await self.session.execute(
            text(
                "SELECT ac.account_id, ac.user_id, r.code AS role_code, COALESCE(ud.name, ac.email) AS name, ud.unit_id, "
                "COALESCE(ud.association_id, b.association_id) AS association_id, u.unit_number, b.name AS block_name "
                "FROM accounts ac JOIN roles r ON r.id = ac.role_id "
                "JOIN user_details ud ON ud.user_id = ac.user_id "
                "LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
                "WHERE ac.account_id = :account_id AND ac.status = :status AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"account_id": account_id, "status": AccountStatus.ACTIVE},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def eligible_residents(self, association_id: str, reporter_user_id: str, reporter_unit_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT ud.user_id, ac.account_id, ud.unit_id, r.code AS role_code, COALESCE(ud.name, ac.email) AS name, u.unit_number, b.name AS block_name "
                "FROM user_details ud JOIN roles r ON r.id = ud.role_id "
                "JOIN accounts ac ON ac.user_id = ud.user_id AND ac.status = :status "
                "LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
                "WHERE r.code IN :resident_role_codes AND ud.is_deleted = 0 "
                "AND COALESCE(ud.association_id, b.association_id) = :association_id "
                "AND ud.user_id <> :reporter_user_id AND ud.unit_id <> :reporter_unit_id ORDER BY name"
            ).bindparams(bindparam("resident_role_codes", expanding=True)),
            {"status": AccountStatus.ACTIVE, "resident_role_codes": (
                RoleCode.HOMEOWNER.value,
                RoleCode.BOARD_MEMBER.value,
                RoleCode.COMMITTEE_MEMBER.value,
            ), "association_id": association_id,
             "reporter_user_id": reporter_user_id, "reporter_unit_id": reporter_unit_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def resident_by_user_id(self, user_id: str) -> dict | None:
        result = await self.session.execute(
            text(
                "SELECT ud.user_id, ac.account_id, r.code AS role_code, COALESCE(ud.name, ac.email) AS name, ud.unit_id, "
                "COALESCE(ud.association_id, b.association_id) AS association_id "
                "FROM user_details ud JOIN roles r ON r.id = ud.role_id "
                "JOIN accounts ac ON ac.user_id = ud.user_id AND ac.status = :status "
                "LEFT JOIN units u ON u.id = ud.unit_id LEFT JOIN blocks b ON b.id = u.block_id "
                "WHERE ud.user_id = :user_id AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"user_id": user_id, "status": AccountStatus.ACTIVE},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def active_account_id_for_user(self, user_id: str | None) -> str | None:
        if not user_id:
            return None
        return await self.session.scalar(
            text("SELECT account_id FROM accounts WHERE user_id = :user_id AND status = :status LIMIT 1"),
            {"user_id": user_id, "status": AccountStatus.ACTIVE},
        )

    async def default_violation_fine(self, association_id: str):
        """Return this association's configured violation fine, if one exists."""
        return await self.session.scalar(
            text(
                "SELECT amount FROM fine_rules WHERE association_id = :association_id "
                "AND LOWER(TRIM(fine_type)) = 'violation' ORDER BY id LIMIT 1"
            ),
            {"association_id": association_id},
        )

    async def admin_association_ids(self, account_id: str) -> list[str]:
        values = await self.session.scalars(text("SELECT association_id FROM admin_associations WHERE admin_id = :account_id"), {"account_id": account_id})
        return list(values.all())

    async def admin_association_ids_for_notifications(self, association_id: str) -> list[str]:
        """Return only administrators assigned to the association, never every admin globally."""
        values = await self.session.scalars(
            text("SELECT admin_id FROM admin_associations WHERE association_id = :association_id"),
            {"association_id": association_id},
        )
        return list(values.all())

    async def member_association_id(self, account_id: str) -> str | None:
        return await self.session.scalar(
            text(
                "SELECT COALESCE(ud.association_id, b.association_id) FROM accounts ac "
                "JOIN user_details ud ON ud.user_id = ac.user_id LEFT JOIN units u ON u.id = ud.unit_id "
                "LEFT JOIN blocks b ON b.id = u.block_id WHERE ac.account_id = :account_id "
                "AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"account_id": account_id},
        )

    async def board_account_ids(self, association_id: str) -> list[str]:
        values = await self.session.scalars(
            text(
                "SELECT bm.account_id FROM board_members bm WHERE bm.association_id = :association_id "
                "AND bm.status = 'active' AND bm.is_deleted = 0 "
                "AND (bm.term_end_date IS NULL OR bm.term_end_date >= CURRENT_DATE)"
            ),
            {"association_id": association_id},
        )
        return list(values.all())

    async def list_rows(self, association_id: str, scope: str, account_id: str | None = None, user_id: str | None = None) -> list[dict]:
        return await self.list_rows_for_associations([association_id], scope, account_id, user_id)

    async def list_rows_for_associations(
        self,
        association_ids: list[str] | None,
        scope: str,
        account_id: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        predicates: list[str] = []
        params: dict[str, object] = {}
        if association_ids is not None:
            if not association_ids:
                return []
            association_params = []
            for index, association_id in enumerate(association_ids):
                key = f"association_id_{index}"
                association_params.append(f":{key}")
                params[key] = association_id
            predicates.append(f"v.association_id IN ({', '.join(association_params)})")
        if scope == "my_violations":
            predicates.append("v.reporter_account_id = :account_id")
            params["account_id"] = account_id
        elif scope == "against_me":
            # The reported homeowner must be able to see a report as soon as it
            # is filed. Their response remains unavailable until Board approval.
            predicates.extend(
                [
                    "v.violator_user_id = :user_id",
                    "v.status IN ('New', 'Pending Board', 'Approved')",
                ]
            )
            params["user_id"] = user_id
        elif scope == "new_admin":
            predicates.append("v.status = 'New'")
        elif scope == "pending_board":
            predicates.append("v.status = 'Pending Board'")
        elif scope == "approved":
            predicates.append("v.status = 'Approved'")
        elif scope == "active":
            predicates.extend(
                [
                    "v.status = 'Approved'",
                    "v.action = 'Fine'",
                    "v.violator_response = 'Accept'",
                    "COALESCE(v.fine_applied, 0) = 0",
                ]
            )
        elif scope == "dismissed":
            predicates.append("v.status IN ('Rejected', 'Dismissed')")
        elif scope == "board_all":
            pass
        elif scope == "all":
            pass
        else:
            raise ValueError("Unsupported violation scope")
        return await self._rows(" AND ".join(predicates), params)

    async def detail_row(self, violation_id: str) -> dict | None:
        rows = await self._rows("v.id = :violation_id", {"violation_id": violation_id})
        return rows[0] if rows else None

    async def _rows(self, predicate: str, params: dict) -> list[dict]:
        where_clause = f"WHERE {predicate}" if predicate else ""
        result = await self.session.execute(
            text(
                "SELECT v.id, v.display_id, v.association_id, v.title, v.category, v.incident_at, v.description, v.violator_user_id, "
                "v.proof_url, v.audio_url, v.knows_violator, v.status, v.offense_count, v.action, v.fine_amount, v.fine_applied, v.admin_notes, "
                "v.board_notes, v.violator_response, v.responded_at, v.created_at, v.updated_at, "
                "COALESCE(reporter_details.name, reporter.email) AS reporter_name, reporter_unit.unit_number AS reporter_unit_number, "
                "COALESCE(violator_details.name, violator.email) AS violator_name, violator_unit.unit_number AS violator_unit_number "
                "FROM violations v JOIN accounts reporter ON reporter.account_id = v.reporter_account_id "
                "LEFT JOIN accounts violator ON violator.account_id = v.violator_account_id "
                "LEFT JOIN user_details reporter_details ON reporter_details.user_id = reporter.user_id "
                "LEFT JOIN user_details violator_details ON violator_details.user_id = v.violator_user_id "
                "LEFT JOIN units reporter_unit ON reporter_unit.id = v.reporter_unit_id "
                "LEFT JOIN units violator_unit ON violator_unit.id = v.violator_unit_id "
                f"{where_clause} ORDER BY v.created_at DESC"
            ),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    async def active_fine_rows_for_homeowner(self, homeowner_user_id: str) -> list[dict]:
        """Return only homeowner-accepted, board-approved Fine violations."""
        result = await self.session.execute(
            text(
                "SELECT id, display_id, title, category, fine_amount FROM violations "
                "WHERE violator_user_id = :homeowner_user_id AND status = 'Approved' "
                "AND action = 'Fine' AND violator_response = 'Accept' "
                "AND COALESCE(fine_applied, 0) = 0 "
                "ORDER BY created_at DESC"
            ),
            {"homeowner_user_id": homeowner_user_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def messages(self, violation_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT m.id, m.violation_id, m.sender_account_id, COALESCE(ud.name, ac.email) AS sender_name, "
                "m.body, m.attachment_url, m.created_at FROM violation_messages m "
                "JOIN accounts ac ON ac.account_id = m.sender_account_id "
                "LEFT JOIN user_details ud ON ud.user_id = ac.user_id WHERE m.violation_id = :violation_id ORDER BY m.created_at"
            ),
            {"violation_id": violation_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def message_row(self, message_id: str) -> dict | None:
        result = await self.session.execute(
            text(
                "SELECT m.id, m.violation_id, m.sender_account_id, COALESCE(ud.name, ac.email) AS sender_name, "
                "m.body, m.attachment_url, m.created_at FROM violation_messages m JOIN accounts ac ON ac.account_id = m.sender_account_id "
                "LEFT JOIN user_details ud ON ud.user_id = ac.user_id WHERE m.id = :message_id"
            ),
            {"message_id": message_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    def add(self, violation: Violation) -> None:
        self.session.add(violation)

    def add_message(self, message: ViolationThreadMessage) -> None:
        self.session.add(message)

    async def notify(self, account_id: str, violation: Violation, title: str, message: str) -> None:
        await create_notification(self.session, account_id, title, message, notification_type="violation", association_id=violation.association_id, entity_type="violation", entity_id=violation.id, action_url=f"/violations/{violation.id}")

    async def notify_many(self, account_ids: list[str], violation: Violation, title: str, message: str, sender_id: str | None = None) -> None:
        await notify_accounts(self.session, account_ids, title, message, sender_id, notification_type="violation", association_id=violation.association_id, entity_type="violation", entity_id=violation.id, action_url=f"/violations/{violation.id}")
