"""Violations domain rules: role, association, and participant safeguards."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.violations.constants import (
    ADMIN_ROLE_CODES,
    BOARD_ROLE_CODES,
    REPORTER_ROLE_CODES,
    RESIDENT_ROLE_CODES,
    ViolationAction,
    ViolationStatus,
)
from app.modules.violations.messages import ViolationMessage
from app.modules.violations.models import Violation, ViolationThreadMessage
from app.modules.violations.repository import ViolationRepository
from app.modules.violations.schemas import (
    ViolationAdminReviewRequest,
    ViolationBoardDecisionRequest,
    ViolationCreateRequest,
    ViolationMessageRequest,
)


@dataclass(frozen=True)
class ViolationMessageEvent:
    message: dict
    recipient_account_ids: set[str]


class ViolationService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ViolationRepository(session)

    @staticmethod
    def role_code(account: Account) -> RoleCode:
        try:
            return RoleCode(account.role.code)
        except (AttributeError, ValueError) as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ViolationMessage.FORBIDDEN) from exc

    async def eligible_residents(self, account: Account) -> list[dict]:
        self._require_reporter(account)
        reporter = await self.repository.resident_context(account.id)
        if not reporter or not reporter.get("association_id") or not reporter.get("unit_id"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, ViolationMessage.NOT_MAPPED)
        return await self.repository.eligible_residents(
            reporter["association_id"], reporter["user_id"], reporter["unit_id"]
        )

    async def create(self, payload: ViolationCreateRequest, account: Account) -> str:
        self._require_reporter(account)
        reporter = await self.repository.resident_context(account.id)
        target = (
            await self.repository.resident_by_user_id(payload.violator_user_id)
            if payload.violator_user_id
            else None
        )
        if not reporter or not reporter.get("association_id") or not reporter.get("unit_id"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, ViolationMessage.NOT_MAPPED)
        if payload.knows_violator and (
            not target
            or target.get("role_code") not in {role.value for role in RESIDENT_ROLE_CODES}
            or target.get("association_id") != reporter["association_id"]
            or not target.get("unit_id")
            or target["unit_id"] == reporter["unit_id"]
            or target["user_id"] == reporter["user_id"]
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, ViolationMessage.INVALID_TARGET)

        sequence = await self.repository.next_sequence(reporter["association_id"])
        violation = Violation(
            id=str(uuid.uuid4()), association_id=reporter["association_id"], sequence_number=sequence,
            display_id=f"VIO-{sequence:04d}", reporter_account_id=account.id, reporter_unit_id=reporter["unit_id"],
            knows_violator=payload.knows_violator,
            violator_user_id=target["user_id"] if target else None,
            violator_account_id=target["account_id"] if target else None,
            violator_unit_id=target["unit_id"] if target else None,
            title=payload.title,
            category=payload.category,
            incident_at=payload.incident_at,
            description=payload.description,
            proof_url=payload.proof_url,
            audio_url=payload.audio_url,
            status=ViolationStatus.NEW,
        )
        self.repository.add(violation)
        await self.repository.session.flush()
        admin_ids = await self.repository.admin_association_ids_for_notifications(violation.association_id)
        await self.repository.notify_many(admin_ids, violation, f"New violation {violation.display_id}", "A homeowner submitted a violation for review.", account.id)
        return violation.id

    async def list(self, scope: str, association_id: str | None, account: Account) -> list[dict]:
        role = self.role_code(account)
        if scope in {"my_violations", "against_me"}:
            self._require_reporter(account)
            association = await self.repository.member_association_id(account.id)
            if not association:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, ViolationMessage.NOT_MAPPED)
            rows = await self.repository.list_rows(association, scope, account.id, account.user_id)
            if scope == "against_me":
                rows = self._hide_reporter_identity(rows)
            return self._mark_current_user_violator(rows, account.user_id)
        if scope in {"new_admin", "dismissed", "all"}:
            return await self._list_admin_rows(scope, association_id, account)
        if scope in {"pending_board", "approved", "active", "board_all"}:
            if role not in BOARD_ROLE_CODES | ADMIN_ROLE_CODES:
                raise HTTPException(status.HTTP_403_FORBIDDEN, ViolationMessage.FORBIDDEN)
            if role in ADMIN_ROLE_CODES:
                return await self._list_admin_rows(scope, association_id, account)
            association = await self._staff_association(account, association_id)
            rows = await self.repository.list_rows(association, scope)
            return self._mark_current_user_violator(self._hide_reporter_identity(rows), account.user_id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported violation list.")

    async def detail(self, violation_id: str, account: Account) -> dict:
        violation = await self._authorized_violation(violation_id, account, allow_admin_read=True)
        row = await self.repository.detail_row(violation.id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, ViolationMessage.NOT_FOUND)
        self._mark_current_user_violator([row], account.user_id)
        if self.role_code(account) not in ADMIN_ROLE_CODES and account.id != violation.reporter_account_id:
            return self._hide_reporter_identity([row])[0]
        return row

    async def admin_review(self, violation_id: str, payload: ViolationAdminReviewRequest, account: Account) -> None:
        self._require_admin(account)
        violation = await self._authorized_violation(violation_id, account, allow_admin_read=True)
        if violation.status != ViolationStatus.NEW:
            raise HTTPException(status.HTTP_409_CONFLICT, ViolationMessage.INVALID_STATUS)
        violator_account_id = await self.repository.active_account_id_for_user(violation.violator_user_id)
        if payload.action == ViolationAction.FINE and not violator_account_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A fine requires the reported homeowner to have an active account.")
        fine_amount = payload.fine_amount
        if payload.action == ViolationAction.FINE and fine_amount is None:
            fine_amount = await self.repository.default_violation_fine(violation.association_id)
            if fine_amount is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, ViolationMessage.FINE_SETUP_REQUIRED)
        violation.violator_account_id = violator_account_id
        violation.offense_count = payload.offense_count
        violation.action = payload.action
        violation.fine_amount = fine_amount if payload.action == ViolationAction.FINE else None
        violation.admin_notes = payload.admin_notes
        violation.status = payload.outcome
        await self.repository.session.flush()
        if payload.outcome == ViolationStatus.PENDING_BOARD:
            await self.repository.notify_many(await self.repository.board_account_ids(violation.association_id), violation, f"Board review needed: {violation.display_id}", "A violation is ready for a board decision.", account.id)
        else:
            await self.repository.notify(violation.reporter_account_id, violation, f"Violation {violation.display_id} updated", f"Your report was {payload.outcome.value.lower()}.")

    async def fine_default(self, violation_id: str, account: Account) -> dict:
        """Read the configured violation fine for an admin-authorized record."""
        self._require_admin(account)
        violation = await self._authorized_violation(violation_id, account, allow_admin_read=True)
        return {"amount": await self.repository.default_violation_fine(violation.association_id)}

    async def homeowner_active_fines(self, account: Account) -> list[dict]:
        self._require_reporter(account)
        return await self.repository.active_fine_rows_for_homeowner(account.user_id)

    async def board_decision(self, violation_id: str, payload: ViolationBoardDecisionRequest, account: Account) -> None:
        self._require_board(account)
        violation = await self._authorized_violation(violation_id, account, allow_admin_read=False)
        if violation.violator_user_id == account.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ViolationMessage.SELF_DECISION_FORBIDDEN)
        if violation.status != ViolationStatus.PENDING_BOARD:
            raise HTTPException(status.HTTP_409_CONFLICT, ViolationMessage.INVALID_STATUS)
        violation.board_notes = payload.board_notes
        violation.status = payload.outcome
        await self.repository.session.flush()
        if payload.outcome == ViolationStatus.APPROVED:
            violator_account_id = await self.repository.active_account_id_for_user(violation.violator_user_id)
            if violator_account_id:
                message = (
                    "A board-approved violation requires your response."
                    if violation.action == ViolationAction.FINE
                    else "A board-approved violation was waived off; no response is required."
                )
                await self.repository.notify(violator_account_id, violation, f"Violation {violation.display_id} approved", message)
        else:
            await self.repository.notify(violation.reporter_account_id, violation, f"Violation {violation.display_id} rejected", "The board rejected this violation.")

    async def respond(self, violation_id: str, response: str, account: Account) -> None:
        violation = await self._authorized_violation(violation_id, account, allow_admin_read=False)
        if (
            violation.violator_user_id != account.user_id
            or violation.status != ViolationStatus.APPROVED
            or violation.action != ViolationAction.FINE
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, ViolationMessage.FORBIDDEN)
        if violation.violator_response is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, ViolationMessage.RESPONSE_ALREADY_RECORDED)
        violation.violator_response = response
        violation.responded_at = datetime.now(UTC)
        await self.repository.session.flush()
        await self.repository.notify(violation.reporter_account_id, violation, f"Response to {violation.display_id}", "The reported homeowner submitted a response.")
        await self.repository.notify_many(await self.repository.board_account_ids(violation.association_id), violation, f"Response to {violation.display_id}", "The reported homeowner submitted a response.", account.id)

    async def messages(self, violation_id: str, account: Account) -> list[dict]:
        await self._authorized_violation(violation_id, account, allow_admin_read=False, require_message_participant=True)
        return await self.repository.messages(violation_id)

    async def send_message(self, violation_id: str, payload: ViolationMessageRequest, account: Account) -> ViolationMessageEvent:
        violation = await self._authorized_violation(violation_id, account, allow_admin_read=False, require_message_participant=True)
        message = ViolationThreadMessage(id=str(uuid.uuid4()), violation_id=violation.id, sender_account_id=account.id, body=payload.body, attachment_url=payload.attachment_url)
        self.repository.add_message(message)
        await self.repository.session.flush()
        message_row = await self.repository.message_row(message.id)
        if message_row is None:
            raise RuntimeError("Persisted violation message could not be loaded")
        recipients = {
            account_id
            for account_id in {
                violation.reporter_account_id,
                await self.repository.active_account_id_for_user(violation.violator_user_id),
                *await self.repository.board_account_ids(violation.association_id),
            }
            if account_id
        }
        await self.repository.notify_many(list(recipients), violation, f"New message: {violation.display_id}", "There is a new message on a violation.", account.id)
        return ViolationMessageEvent(message=message_row, recipient_account_ids=recipients)

    async def _authorized_violation(self, violation_id: str, account: Account, *, allow_admin_read: bool, require_message_participant: bool = False) -> Violation:
        violation = await self.repository.get(violation_id)
        if violation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, ViolationMessage.NOT_FOUND)
        role = self.role_code(account)
        if account.id == violation.reporter_account_id:
            return violation
        if account.user_id == violation.violator_user_id and violation.status == ViolationStatus.APPROVED:
            return violation
        association = await self.repository.member_association_id(account.id)
        if role in BOARD_ROLE_CODES and association == violation.association_id:
            return violation
        if allow_admin_read and role in ADMIN_ROLE_CODES and await self._admin_has_association(account, violation.association_id):
            return violation
        raise HTTPException(status.HTTP_403_FORBIDDEN, ViolationMessage.FORBIDDEN)

    @staticmethod
    def _hide_reporter_identity(rows: list[dict]) -> list[dict]:
        for row in rows:
            row["reporter_name"] = None
            row["reporter_unit_number"] = None
        return rows

    @staticmethod
    def _mark_current_user_violator(rows: list[dict], user_id: str | None) -> list[dict]:
        for row in rows:
            row["is_current_user_violator"] = bool(user_id and row.get("violator_user_id") == user_id)
            row.pop("violator_user_id", None)
        return rows

    def _require_reporter(self, account: Account) -> None:
        if self.role_code(account) not in REPORTER_ROLE_CODES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ViolationMessage.FORBIDDEN)

    def _require_admin(self, account: Account) -> None:
        if self.role_code(account) not in ADMIN_ROLE_CODES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ViolationMessage.FORBIDDEN)

    def _require_board(self, account: Account) -> None:
        if self.role_code(account) not in BOARD_ROLE_CODES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ViolationMessage.FORBIDDEN)

    async def _list_admin_rows(
        self,
        scope: str,
        association_id: str | None,
        account: Account,
    ) -> list[dict]:
        self._require_admin(account)
        if association_id:
            association = await self._admin_association(account, association_id)
            return await self.repository.list_rows(association, scope)

        if self.role_code(account) == RoleCode.SUPER_ADMIN:
            return await self.repository.list_rows_for_associations(None, scope)

        association_ids = await self.repository.admin_association_ids(account.id)
        return await self.repository.list_rows_for_associations(association_ids, scope)

    async def _admin_has_association(self, account: Account, association_id: str) -> bool:
        return self.role_code(account) == RoleCode.SUPER_ADMIN or association_id in await self.repository.admin_association_ids(account.id)

    async def _admin_association(self, account: Account, association_id: str | None) -> str:
        if association_id and await self._admin_has_association(account, association_id):
            return association_id
        if not association_id and self.role_code(account) != RoleCode.SUPER_ADMIN:
            values = await self.repository.admin_association_ids(account.id)
            if len(values) == 1:
                return values[0]
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Select an association you administer.")

    async def _staff_association(self, account: Account, association_id: str | None) -> str:
        if self.role_code(account) in ADMIN_ROLE_CODES:
            return await self._admin_association(account, association_id)
        association = await self.repository.member_association_id(account.id)
        if association and (association_id is None or association_id == association):
            return association
        raise HTTPException(status.HTTP_403_FORBIDDEN, ViolationMessage.FORBIDDEN)
