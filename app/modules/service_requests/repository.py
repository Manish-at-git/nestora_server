"""Database access for service-request tickets, lookup data, and notifications."""

import uuid
from collections.abc import Iterable

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AccountStatus, RoleCode
from app.modules.auth.models import Account
from app.modules.notifications.service import create_notification, notify_accounts
from app.modules.service_requests.models import ServiceRequest, ServiceRequestThreadMessage


class ServiceRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, request_id: str) -> ServiceRequest | None:
        return await self.session.scalar(
            select(ServiceRequest).where(
                ServiceRequest.id == request_id,
                ServiceRequest.is_deleted.is_(False),
            )
        )

    async def get_detail(self, request_id: str) -> dict | None:
        result = await self.session.execute(
            text(
                "SELECT sr.id, sr.user_id, sr.association_id, sr.unit_id, sr.sr_display_id, "
                "sr.service_type, sr.sub_category, sr.custom_title, sr.description, sr.image_url, "
                "sr.status, sr.incoming_call_no, sr.created_at, sr.updated_at, "
                "u.unit_number, b.name AS block_name, a.name AS association_name, "
                "ud.name AS requestor_name, ud.contact_number AS requestor_phone, "
                "COALESCE(ac.email, ud.email) AS requestor_email "
                "FROM service_requests sr "
                "LEFT JOIN units u ON sr.unit_id = u.id "
                "LEFT JOIN blocks b ON u.block_id = b.id "
                "LEFT JOIN associations a ON sr.association_id = a.id "
                "LEFT JOIN accounts ac ON sr.user_id = ac.account_id "
                "LEFT JOIN user_details ud ON (ac.user_id = ud.user_id OR sr.user_id = ud.user_id) "
                "WHERE sr.id = :request_id AND sr.is_deleted = 0 LIMIT 1"
            ),
            {"request_id": request_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_for_resident(self, account_id: str, user_id: str | None) -> list[dict]:
        identifiers = [account_id]
        if user_id:
            identifiers.append(user_id)
        resident_context = await self.resident_unit_context(account_id, user_id)
        predicate = "sr.user_id IN :identifiers"
        parameters: dict = {"identifiers": tuple(dict.fromkeys(identifiers))}
        if resident_context and resident_context.get("unit_id"):
            predicate = (
                f"({predicate} OR (sr.unit_id = :unit_id "
                "AND sr.association_id = :association_id))"
            )
            parameters.update(
                {
                    "unit_id": resident_context["unit_id"],
                    "association_id": resident_context.get("association_id"),
                }
            )
        return await self._list(predicate, parameters)

    async def resident_unit_context(
        self, account_id: str, user_id: str | None
    ) -> dict | None:
        identifiers = [account_id]
        if user_id:
            identifiers.append(user_id)
        result = await self.session.execute(
            text(
                "SELECT ud.unit_id, COALESCE(ud.association_id, b.association_id) AS association_id "
                "FROM user_details ud "
                "LEFT JOIN units u ON ud.unit_id = u.id "
                "LEFT JOIN blocks b ON u.block_id = b.id "
                "WHERE ud.user_id IN :identifiers AND ud.is_deleted = 0 "
                "AND ud.unit_id IS NOT NULL LIMIT 1"
            ).bindparams(bindparam("identifiers", expanding=True)),
            {"identifiers": tuple(dict.fromkeys(identifiers))},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_for_associations(
        self,
        association_ids: Iterable[str],
        include_unassigned: bool = False,
    ) -> list[dict]:
        ids = tuple(dict.fromkeys(association_ids))
        if not ids:
            return await self._list("sr.association_id IS NULL", {}) if include_unassigned else []
        predicate = "sr.association_id IN :association_ids"
        if include_unassigned:
            predicate = f"({predicate} OR sr.association_id IS NULL)"
        return await self._list(predicate, {"association_ids": ids})

    async def list_all(self) -> list[dict]:
        return await self._list("1 = 1", {})

    async def _list(self, predicate: str, parameters: dict) -> list[dict]:
        statement = text(
            "SELECT sr.id, sr.user_id, sr.association_id, sr.unit_id, sr.sr_display_id, "
            "sr.service_type, sr.sub_category, sr.custom_title, sr.description, sr.image_url, "
            "sr.status, sr.incoming_call_no, sr.created_at, sr.updated_at, "
            "u.unit_number, b.name AS block_name, a.name AS association_name, "
            "ud.name AS requestor_name, ud.contact_number AS requestor_phone, "
            "COALESCE(ac.email, ud.email) AS requestor_email "
            "FROM service_requests sr "
            "LEFT JOIN units u ON sr.unit_id = u.id "
            "LEFT JOIN blocks b ON u.block_id = b.id "
            "LEFT JOIN associations a ON sr.association_id = a.id "
            "LEFT JOIN accounts ac ON sr.user_id = ac.account_id "
            "LEFT JOIN user_details ud ON (ac.user_id = ud.user_id OR sr.user_id = ud.user_id) "
            f"WHERE sr.is_deleted = 0 AND {predicate} ORDER BY sr.created_at DESC"
        )
        if "association_ids" in parameters:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        if "identifiers" in parameters:
            statement = statement.bindparams(bindparam("identifiers", expanding=True))
        result = await self.session.execute(statement, parameters)
        return [dict(row) for row in result.mappings().all()]

    async def admin_association_ids(self, account_id: str) -> list[str]:
        result = await self.session.scalars(
            text("SELECT association_id FROM admin_associations WHERE admin_id = :account_id"),
            {"account_id": account_id},
        )
        return list(result.all())

    async def member_association_id(self, account: Account) -> str | None:
        if not account.user_id:
            return None
        result = await self.session.execute(
            text(
                "SELECT COALESCE(ud.association_id, b.association_id) AS association_id "
                "FROM user_details ud "
                "LEFT JOIN units u ON ud.unit_id = u.id "
                "LEFT JOIN blocks b ON u.block_id = b.id "
                "WHERE ud.user_id = :user_id AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"user_id": account.user_id},
        )
        row = result.mappings().first()
        return row["association_id"] if row else None

    async def resident_context(self, identifier: str) -> dict | None:
        result = await self.session.execute(
            text(
                "SELECT COALESCE(ac.account_id, ud.user_id) AS request_user_id, ac.account_id, "
                "ud.user_id, ud.name, COALESCE(ac.email, ud.email) AS email, ud.unit_id, "
                "COALESCE(ud.association_id, b.association_id) AS association_id, "
                "a.name AS association_name, b.name AS block_name, u.unit_number "
                "FROM user_details ud "
                "LEFT JOIN accounts ac ON ac.user_id = ud.user_id "
                "LEFT JOIN units u ON ud.unit_id = u.id "
                "LEFT JOIN blocks b ON u.block_id = b.id "
                "LEFT JOIN associations a ON COALESCE(ud.association_id, b.association_id) = a.id "
                "WHERE (ac.account_id = :identifier OR ud.user_id = :identifier) "
                "AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"identifier": identifier},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def next_display_sequence(self, unit_id: str | None) -> int:
        statement = select(func.count(ServiceRequest.id))
        if unit_id:
            statement = statement.where(ServiceRequest.unit_id == unit_id)
        return int(await self.session.scalar(statement) or 0) + 1

    def add(self, request: ServiceRequest) -> None:
        self.session.add(request)

    async def unit_belongs_to_association(self, unit_id: str, association_id: str) -> bool:
        result = await self.session.execute(
            text(
                "SELECT u.id FROM units u JOIN blocks b ON u.block_id = b.id "
                "WHERE u.id = :unit_id AND b.association_id = :association_id LIMIT 1"
            ),
            {"unit_id": unit_id, "association_id": association_id},
        )
        return result.first() is not None

    async def resident_belongs_to_unit(self, identifier: str, unit_id: str) -> bool:
        result = await self.session.execute(
            text(
                "SELECT ud.user_id FROM user_details ud "
                "LEFT JOIN accounts ac ON ac.user_id = ud.user_id "
                "WHERE (ud.user_id = :identifier OR ac.account_id = :identifier) "
                "AND ud.unit_id = :unit_id AND ud.is_deleted = 0 LIMIT 1"
            ),
            {"identifier": identifier, "unit_id": unit_id},
        )
        return result.first() is not None

    async def blocks(self, association_id: str) -> list[dict]:
        result = await self.session.execute(
            text("SELECT id, name FROM blocks WHERE association_id = :id ORDER BY name"),
            {"id": association_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def units(self, association_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT u.id, u.unit_number, b.name AS block_name FROM units u "
                "JOIN blocks b ON u.block_id = b.id WHERE b.association_id = :id "
                "ORDER BY b.name, u.unit_number"
            ),
            {"id": association_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def block_units(self, block_id: str) -> list[dict]:
        result = await self.session.execute(
            text("SELECT id, unit_number FROM units WHERE block_id = :id ORDER BY unit_number"),
            {"id": block_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def block_association_id(self, block_id: str) -> str | None:
        return await self.session.scalar(
            text("SELECT association_id FROM blocks WHERE id = :id LIMIT 1"),
            {"id": block_id},
        )

    async def unit_association_id(self, unit_id: str) -> str | None:
        return await self.session.scalar(
            text(
                "SELECT b.association_id FROM units u JOIN blocks b ON u.block_id = b.id "
                "WHERE u.id = :id LIMIT 1"
            ),
            {"id": unit_id},
        )

    async def residents(self, unit_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT COALESCE(ac.account_id, ud.user_id) AS user_id, ud.name, ud.first_name, "
                "ud.last_name, COALESCE(ac.email, ud.email) AS email FROM user_details ud "
                "LEFT JOIN accounts ac ON ud.user_id = ac.user_id "
                "WHERE ud.unit_id = :id AND ud.is_deleted = 0 ORDER BY ud.name"
            ),
            {"id": unit_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def messages(self, request_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT m.id, m.service_request_id, m.sender_id, m.message, m.attachment_url, "
                "m.created_at, a.email, a.role_id, ud.name AS sender_name "
                "FROM service_request_messages m JOIN accounts a ON m.sender_id = a.account_id "
                "LEFT JOIN user_details ud ON a.user_id = ud.user_id "
                "WHERE m.service_request_id = :request_id ORDER BY m.created_at"
            ),
            {"request_id": request_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def message_event(self, message_id: str) -> dict | None:
        result = await self.session.execute(
            text(
                "SELECT m.id, m.service_request_id, m.sender_id, m.message, m.attachment_url, "
                "m.created_at, a.email, a.role_id, ud.name AS sender_name "
                "FROM service_request_messages m JOIN accounts a ON m.sender_id = a.account_id "
                "LEFT JOIN user_details ud ON a.user_id = ud.user_id "
                "WHERE m.id = :message_id LIMIT 1"
            ),
            {"message_id": message_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def participant_account_ids(self, request: ServiceRequest) -> set[str]:
        """Resolve accounts allowed to receive this request's chat event."""
        participant_ids: set[str] = set()
        resident = await self.resident_context(request.user_id) if request.user_id else None
        if resident and resident.get("account_id"):
            participant_ids.add(resident["account_id"])

        if request.unit_id and request.association_id:
            unit_residents = await self.session.scalars(
                text(
                    "SELECT DISTINCT ac.account_id FROM accounts ac "
                    "JOIN user_details ud ON ud.user_id = ac.user_id "
                    "WHERE ac.status = :account_status AND ud.unit_id = :unit_id "
                    "AND COALESCE(ud.association_id, "
                    "(SELECT b.association_id FROM units u JOIN blocks b ON u.block_id = b.id "
                    "WHERE u.id = ud.unit_id LIMIT 1)) = :association_id "
                    "AND ud.is_deleted = 0"
                ),
                {
                    "account_status": AccountStatus.ACTIVE,
                    "unit_id": request.unit_id,
                    "association_id": request.association_id,
                },
            )
            participant_ids.update(unit_residents.all())

        if request.association_id:
            admin_result = await self.session.scalars(
                text(
                    "SELECT admin_id FROM admin_associations "
                    "WHERE association_id = :association_id"
                ),
                {"association_id": request.association_id},
            )
            participant_ids.update(admin_result.all())

            staff_result = await self.session.scalars(
                text(
                    "SELECT DISTINCT ac.account_id FROM accounts ac "
                    "JOIN roles r ON r.id = ac.role_id "
                    "JOIN user_details ud ON ud.user_id = ac.user_id "
                    "LEFT JOIN units u ON u.id = ud.unit_id "
                    "LEFT JOIN blocks b ON b.id = u.block_id "
                    "WHERE ac.status = :account_status AND r.code IN :role_codes "
                    "AND r.is_active = 1 "
                    "AND r.is_deleted = 0 AND ud.is_deleted = 0 "
                    "AND COALESCE(ud.association_id, b.association_id) = :association_id"
                ).bindparams(bindparam("role_codes", expanding=True)),
                {
                    "role_codes": (
                        RoleCode.SECURITY,
                        RoleCode.BOARD_MEMBER,
                        RoleCode.COMMITTEE_MEMBER,
                    ),
                    "account_status": AccountStatus.ACTIVE,
                    "association_id": request.association_id,
                },
            )
            participant_ids.update(staff_result.all())

        super_admins = await self.session.scalars(
            text(
                "SELECT ac.account_id FROM accounts ac JOIN roles r ON r.id = ac.role_id "
                "WHERE ac.status = :account_status AND r.code = :role_code "
                "AND r.is_active = 1 AND r.is_deleted = 0"
            ),
            {
                "account_status": AccountStatus.ACTIVE,
                "role_code": RoleCode.SUPER_ADMIN,
            },
        )
        participant_ids.update(super_admins.all())
        return participant_ids

    def add_message(self, message: ServiceRequestThreadMessage) -> None:
        self.session.add(message)

    async def add_notification(
        self,
        account_id: str | None,
        title: str,
        message: str,
        request_id: str | None = None,
    ) -> None:
        if not account_id:
            return
        await create_notification(
            self.session,
            account_id,
            title,
            message,
            notification_type="service_request",
            entity_type="service_request",
            entity_id=request_id,
            action_url=f"/service-requests/{request_id}" if request_id else "/service-requests",
        )

    async def notify_association_admins(
        self,
        association_id: str,
        title: str,
        message: str,
        request_id: str | None = None,
    ) -> None:
        result = await self.session.scalars(
            text("SELECT admin_id FROM admin_associations WHERE association_id = :id"),
            {"id": association_id},
        )
        await notify_accounts(
            self.session,
            result.all(),
            title,
            message,
            notification_type="service_request",
            entity_type="service_request",
            entity_id=request_id,
            action_url=f"/service-requests/{request_id}" if request_id else "/service-requests",
        )
