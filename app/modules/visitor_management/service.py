"""Authorization and workflows for visitor management."""

import secrets
import string
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.notifications.service import notify_accounts
from app.modules.visitor_management import messages
from app.modules.visitor_management.constants import (
    RESIDENT_VISITOR_ROLES,
    SECURITY_VISITOR_ROLES,
    VISITOR_APPROVAL_ACTION_URL,
    VISITOR_ADMIN_ROLES,
    VisitorPassStatus,
    VisitorVisitStatus,
)
from app.modules.visitor_management.repository import VisitorManagementRepository
from app.modules.visitor_management.schemas import (
    DeliveryRequest,
    PreApprovedVisitorRequest,
    VisitorRequest,
)


def _scheduled_datetime(visit_date: date, visit_time: time | timedelta | str) -> datetime:
    """Normalize the MySQL TIME values returned by the async driver."""
    if isinstance(visit_time, timedelta):
        return datetime.combine(visit_date, time.min) + visit_time
    if isinstance(visit_time, str):
        visit_time = time.fromisoformat(visit_time)
    return datetime.combine(visit_date, visit_time)


def _effective_pass_status(visitor_pass: dict) -> dict:
    """Treat an unused pass scheduled before today as expired without altering audit states."""
    resolved_pass = dict(visitor_pass)
    visit_date = resolved_pass.get("visit_date")
    if isinstance(visit_date, datetime):
        visit_date = visit_date.date()
    elif isinstance(visit_date, str):
        visit_date = date.fromisoformat(visit_date[:10])

    if (
        resolved_pass.get("status") == VisitorPassStatus.ACTIVE
        and isinstance(visit_date, date)
        and visit_date < date.today()
    ):
        resolved_pass["status"] = VisitorPassStatus.EXPIRED
    return resolved_pass


class VisitorManagementService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = VisitorManagementRepository(session)

    @staticmethod
    def role(account: Account) -> RoleCode:
        try:
            return RoleCode(account.role.code)
        except (AttributeError, ValueError) as exc:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Visitor management is not available for this role"
            ) from exc

    def require_security(self, account: Account) -> RoleCode:
        role = self.role(account)
        if role not in {*SECURITY_VISITOR_ROLES, *VISITOR_ADMIN_ROLES}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, messages.SECURITY_ACCESS_REQUIRED)
        return role

    def require_resident(self, account: Account) -> RoleCode:
        role = self.role(account)
        if role not in {*RESIDENT_VISITOR_ROLES, *VISITOR_ADMIN_ROLES}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, messages.RESIDENT_ACCESS_REQUIRED)
        return role

    async def security_association_ids(self, account: Account) -> list[str] | None:
        """Return the associations a gate operator may access; super admins remain global."""
        role = self.require_security(account)
        if role == RoleCode.SUPER_ADMIN:
            return None
        return await self.repository.association_ids_for_account(account.id)

    async def security_preapproved(
        self, account: Account, *, search: str | None = None, today: bool = False
    ) -> list[dict]:
        visitors = await self.repository.passes(
            search=search,
            today=today,
            association_ids=await self.security_association_ids(account),
        )
        return [_effective_pass_status(visitor) for visitor in visitors]

    async def search_residents(self, account: Account, query: str) -> list[dict]:
        return await self.repository.resident_search(
            query,
            await self.security_association_ids(account),
        )

    async def search_visitor(self, account: Account, mobile: str) -> dict | None:
        return await self.repository.find_visitor(
            mobile,
            await self.security_association_ids(account),
        )

    async def require_pass_security_access(self, pass_id: str, account: Account) -> None:
        association_ids = await self.security_association_ids(account)
        if association_ids is None:
            return
        if not await self.repository.pass_is_in_associations(pass_id, association_ids):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Visitor pass not found")

    async def resident_unit(self, account: Account) -> str:
        self.require_resident(account)
        unit_id = await self.repository.unit_for_user(account.user_id)
        if not unit_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your account is not assigned to a unit")
        return unit_id

    async def create_request(self, payload: VisitorRequest, account: Account) -> str:
        self.require_security(account)
        association_ids = await self.security_association_ids(account)
        if association_ids is not None and not await self.repository.unit_is_in_associations(
            payload.unit_id,
            association_ids,
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Resident unit not found")
        visitor_id = await self.repository.save_visitor(
            payload.model_dump(
                exclude={
                    "unit_id",
                    "purpose",
                    "visitor_type",
                    "number_of_visitors",
                    "vehicle_number",
                    "expected_duration",
                    "notes",
                }
            )
        )
        visit_id = await self.repository.create_visit(
            {
                "visitor_id": visitor_id,
                "unit_id": payload.unit_id,
                "purpose": payload.purpose,
                "visitor_type": payload.visitor_type,
                "number_of_visitors": payload.number_of_visitors,
                "vehicle_number": payload.vehicle_number,
                "notes": payload.notes,
                "expected_duration": payload.expected_duration,
            }
        )
        resident_account_ids = await self.repository.account_ids_for_unit(payload.unit_id)
        await notify_accounts(
            self.repository.session,
            resident_account_ids,
            "Visitor approval required",
            f"{payload.name} is waiting at the gate for your approval.",
            account.id,
            notification_type="visitor",
            entity_type="visitor_visit",
            entity_id=visit_id,
            action_url=VISITOR_APPROVAL_ACTION_URL,
        )
        return visit_id

    async def approve(self, visit_id: str, account: Account, approved: bool) -> str | None:
        visit = await self.repository.get_visit(visit_id, "Pending")
        if not visit:
            raise HTTPException(status.HTTP_404_NOT_FOUND, messages.VISIT_NOT_FOUND)
        role = self.role(account)
        unit_id = (
            visit["unit_id"]
            if role in {RoleCode.ADMIN, RoleCode.SUPER_ADMIN}
            else await self.resident_unit(account)
        )
        if visit["unit_id"] != unit_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, messages.VISIT_NOT_FOUND)
        if not approved:
            await self.repository.update_visit(visit_id, {"status": VisitorVisitStatus.DENIED})
            return None
        pass_code = "PASS-" + "".join(
            secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4)
        )
        await self.repository.update_visit(
            visit_id,
            {"status": VisitorVisitStatus.APPROVED, "pass_code": pass_code},
        )
        return pass_code

    async def create_preapproved(
        self, payload: PreApprovedVisitorRequest, account: Account
    ) -> tuple[str, str, str]:
        unit_id = await self.resident_unit(account)
        pass_code = "PA-" + "".join(
            secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6)
        )
        otp = "".join(secrets.choice(string.digits) for _ in range(6))
        values = payload.model_dump()
        values.update(
            {
                "resident_id": account.user_id,
                "unit_id": unit_id,
                "pass_code": pass_code,
                "otp": otp,
                "created_by": account.id,
            }
        )
        pass_id = await self.repository.preapproved_create(values)
        return pass_id, pass_code, otp

    async def check_in(self, pass_id: str, payload: dict, account: Account) -> str:
        self.require_security(account)
        await self.require_pass_security_access(pass_id, account)
        visitor_pass = await self.repository.get_pass(pass_id=pass_id)
        if visitor_pass:
            visitor_pass = _effective_pass_status(visitor_pass)
        if not visitor_pass or visitor_pass["status"] != VisitorPassStatus.ACTIVE:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, messages.VISITOR_PASS_INVALID)
        now = datetime.now()
        visit_start = _scheduled_datetime(visitor_pass["visit_date"], visitor_pass["start_time"])
        visit_end = _scheduled_datetime(visitor_pass["visit_date"], visitor_pass["end_time"])
        if not visit_start <= now <= visit_end:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, messages.VISITOR_PASS_OUTSIDE_WINDOW)
        if visitor_pass.get("otp") and payload.get("otp") != visitor_pass["otp"]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, messages.VISITOR_PASS_OTP_INVALID)
        if await self.repository.active_log(pass_id):
            raise HTTPException(status.HTTP_409_CONFLICT, messages.VISITOR_ALREADY_INSIDE)
        log_values = {key: value for key, value in payload.items() if key != "otp"}
        log_id = await self.repository.create_log(
            {"pre_approved_id": pass_id, **log_values, "guard_id": account.id}
        )
        if visitor_pass.get("pass_type") == "Single Entry":
            from sqlalchemy import text

            await self.repository.session.execute(
                text(
                    "UPDATE pre_approved_visitors SET status=:status WHERE id=:id AND is_deleted=0"
                ),
                {"id": pass_id, "status": VisitorPassStatus.USED},
            )
        return log_id

    async def check_in_walk_in(self, visit_id: str, account: Account) -> None:
        self.require_security(account)
        association_ids = await self.security_association_ids(account)
        if association_ids is not None and not await self.repository.visit_is_in_associations(
            visit_id,
            association_ids,
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, messages.VISIT_NOT_FOUND)
        if not await self.repository.check_in_visit(visit_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Visitor request is not approved")

    async def visitor_status(self, visit_id: str, account: Account) -> dict:
        self.require_security(account)
        association_ids = await self.security_association_ids(account)
        if association_ids is not None and not await self.repository.visit_is_in_associations(
            visit_id,
            association_ids,
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, messages.VISIT_NOT_FOUND)
        visit = await self.repository.get_visit(visit_id)
        if not visit:
            raise HTTPException(status.HTTP_404_NOT_FOUND, messages.VISIT_NOT_FOUND)
        return visit

    async def check_out(self, pass_id: str, account: Account) -> str:
        self.require_security(account)
        await self.require_pass_security_access(pass_id, account)
        log = await self.repository.active_log(pass_id)
        if not log:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No active check-in found for this pass")
        await self.repository.close_log(log["id"])
        visitor_pass = await self.repository.get_pass(pass_id=pass_id)
        if visitor_pass and visitor_pass.get("pass_type") == "Single Entry":
            from sqlalchemy import text

            await self.repository.session.execute(
                text(
                    "UPDATE pre_approved_visitors SET status='Expired' WHERE id=:id AND is_deleted=0"
                ),
                {"id": pass_id},
            )
        return log["id"]

    async def check_out_log(self, log_id: str, account: Account) -> None:
        self.require_security(account)
        association_ids = await self.security_association_ids(account)
        if association_ids is not None and not await self.repository.log_is_in_associations(
            log_id,
            association_ids,
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, messages.ACTIVE_VISIT_NOT_FOUND)
        log = await self.repository.get_log(log_id)
        if not log or log.get("check_out") is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No active check-in found for this log")
        await self.repository.close_log(log_id)
        visitor_pass = await self.repository.get_pass(pass_id=log["pre_approved_id"])
        if visitor_pass and visitor_pass.get("pass_type") == "Single Entry":
            from sqlalchemy import text

            await self.repository.session.execute(
                text(
                    "UPDATE pre_approved_visitors SET status='Expired' WHERE id=:id AND is_deleted=0"
                ),
                {"id": log["pre_approved_id"]},
            )

    async def check_out_walk_in(self, visit_id: str, account: Account) -> None:
        self.require_security(account)
        association_ids = await self.security_association_ids(account)
        if association_ids is not None and not await self.repository.visit_is_in_associations(
            visit_id,
            association_ids,
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, messages.ACTIVE_VISIT_NOT_FOUND)
        if not await self.repository.check_out_visit(visit_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, messages.ACTIVE_VISIT_NOT_FOUND)

    async def resident_history(self, account: Account) -> list[dict]:
        return await self.repository.history(unit_id=await self.resident_unit(account))

    async def resident_gate_request_history(self, account: Account) -> list[dict]:
        return await self.repository.gate_request_history(unit_id=await self.resident_unit(account))

    async def security_active(self, account: Account) -> list[dict]:
        return await self.repository.active_visitors(await self.security_association_ids(account))

    async def security_gate_requests(self, account: Account) -> list[dict]:
        self.require_security(account)
        return await self.repository.security_gate_requests(
            await self.security_association_ids(account)
        )

    async def security_gate_request_history(self, account: Account) -> list[dict]:
        self.require_security(account)
        return await self.repository.gate_request_history(
            association_ids=await self.security_association_ids(account)
        )

    async def security_history(self, account: Account) -> list[dict]:
        return await self.repository.history(
            association_ids=await self.security_association_ids(account)
        )

    async def create_delivery(self, payload: DeliveryRequest, account: Account) -> str:
        self.require_security(account)
        return await self.repository.create_delivery(
            {**payload.model_dump(), "guard_id": account.id, "resident_id": None}
        )

    async def complete_delivery(self, delivery_id: str, account: Account) -> None:
        self.require_security(account)
        if not await self.repository.complete_delivery(delivery_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Delivery not found")
