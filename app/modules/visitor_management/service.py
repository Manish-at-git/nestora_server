"""Authorization and workflows for visitor management."""

import secrets
import string

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.visitor_management.repository import VisitorManagementRepository
from app.modules.visitor_management.schemas import DeliveryRequest, PreApprovedVisitorRequest, VisitorRequest


RESIDENT_ROLES = {RoleCode.HOMEOWNER, RoleCode.TENANT, RoleCode.BOARD_MEMBER, RoleCode.COMMITTEE_MEMBER}
SECURITY_ROLES = {RoleCode.SECURITY, RoleCode.ADMIN, RoleCode.SUPER_ADMIN}


class VisitorManagementService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = VisitorManagementRepository(session)

    @staticmethod
    def role(account: Account) -> RoleCode:
        try:
            return RoleCode(account.role.code)
        except (AttributeError, ValueError) as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Visitor management is not available for this role") from exc

    def require_security(self, account: Account) -> RoleCode:
        role = self.role(account)
        if role not in SECURITY_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Security access is required")
        return role

    async def resident_unit(self, account: Account) -> str:
        role = self.role(account)
        if role not in RESIDENT_ROLES and role not in {RoleCode.ADMIN, RoleCode.SUPER_ADMIN}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Resident access is required")
        unit_id = await self.repository.unit_for_user(account.user_id)
        if not unit_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your account is not assigned to a unit")
        return unit_id

    async def create_request(self, payload: VisitorRequest, account: Account) -> str:
        self.require_security(account)
        visitor_id = await self.repository.save_visitor(payload.model_dump(exclude={"unit_id", "purpose", "visitor_type", "number_of_visitors", "vehicle_number", "expected_duration", "notes"}))
        return await self.repository.create_visit({
            "visitor_id": visitor_id,
            "unit_id": payload.unit_id,
            "purpose": payload.purpose,
            "visitor_type": payload.visitor_type,
            "number_of_visitors": payload.number_of_visitors,
            "vehicle_number": payload.vehicle_number,
            "notes": payload.notes,
            "expected_duration": payload.expected_duration,
        })

    async def approve(self, visit_id: str, account: Account, approved: bool) -> str | None:
        visit = await self.repository.get_visit(visit_id, "Pending")
        if not visit:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Visit not found or already processed")
        role = self.role(account)
        unit_id = visit["unit_id"] if role in {RoleCode.ADMIN, RoleCode.SUPER_ADMIN} else await self.resident_unit(account)
        if visit["unit_id"] != unit_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Visit not found or already processed")
        if not approved:
            await self.repository.update_visit(visit_id, {"status": "Denied"})
            return None
        pass_code = "PASS-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        await self.repository.update_visit(visit_id, {"status": "Approved", "pass_code": pass_code})
        return pass_code

    async def create_preapproved(self, payload: PreApprovedVisitorRequest, account: Account) -> tuple[str, str, str]:
        unit_id = await self.resident_unit(account)
        pass_code = "PA-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        otp = "".join(secrets.choice(string.digits) for _ in range(6))
        values = payload.model_dump()
        values.update({"resident_id": account.user_id, "unit_id": unit_id, "pass_code": pass_code, "otp": otp, "created_by": account.id})
        pass_id = await self.repository.preapproved_create(values)
        return pass_id, pass_code, otp

    async def check_in(self, pass_id: str, payload: dict, account: Account) -> str:
        self.require_security(account)
        visitor_pass = await self.repository.get_pass(pass_id=pass_id)
        if not visitor_pass or visitor_pass["status"] not in {"Active", "Used"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pass is not valid for check-in")
        if await self.repository.active_log(pass_id):
            raise HTTPException(status.HTTP_409_CONFLICT, "This pass is already checked in")
        log_values = {key: value for key, value in payload.items() if key != "guard_id"}
        log_id = await self.repository.create_log({"pre_approved_id": pass_id, **log_values, "guard_id": account.id})
        if visitor_pass.get("pass_type") == "Single Entry":
            from sqlalchemy import text
            await self.repository.session.execute(text("UPDATE pre_approved_visitors SET status='Used' WHERE id=:id AND is_deleted=0"), {"id": pass_id})
        return log_id

    async def check_out(self, pass_id: str, account: Account) -> str:
        self.require_security(account)
        log = await self.repository.active_log(pass_id)
        if not log:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No active check-in found for this pass")
        await self.repository.close_log(log["id"])
        visitor_pass = await self.repository.get_pass(pass_id=pass_id)
        if visitor_pass and visitor_pass.get("pass_type") == "Single Entry":
            from sqlalchemy import text
            await self.repository.session.execute(text("UPDATE pre_approved_visitors SET status='Expired' WHERE id=:id AND is_deleted=0"), {"id": pass_id})
        return log["id"]

    async def check_out_log(self, log_id: str, account: Account) -> None:
        self.require_security(account)
        log = await self.repository.get_log(log_id)
        if not log or log.get("check_out") is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No active check-in found for this log")
        await self.repository.close_log(log_id)
        visitor_pass = await self.repository.get_pass(pass_id=log["pre_approved_id"])
        if visitor_pass and visitor_pass.get("pass_type") == "Single Entry":
            from sqlalchemy import text
            await self.repository.session.execute(text("UPDATE pre_approved_visitors SET status='Expired' WHERE id=:id AND is_deleted=0"), {"id": log["pre_approved_id"]})

    async def create_delivery(self, payload: DeliveryRequest, account: Account) -> str:
        self.require_security(account)
        return await self.repository.create_delivery({**payload.model_dump(), "guard_id": account.id, "resident_id": None})

    async def complete_delivery(self, delivery_id: str, account: Account) -> None:
        self.require_security(account)
        if not await self.repository.complete_delivery(delivery_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Delivery not found")
