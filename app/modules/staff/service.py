"""Role-aware staff directory, attendance, and monthly reporting workflows."""

from calendar import monthrange
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.access_codes import generate_access_code, normalize_access_code
from app.core.contact_normalization import normalize_email
from app.core.security import hash_password
from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.staff.models import StaffMember
from app.modules.staff.repository import StaffRepository
from app.modules.staff.schemas import StaffCreateRequest, StaffPastAttendanceRequest, StaffUpdateRequest


STAFF_MANAGER_ROLES = {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}
STAFF_OPERATOR_ROLES = {*STAFF_MANAGER_ROLES, RoleCode.SECURITY}


class StaffService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = StaffRepository(session)

    @staticmethod
    def role(account: Account) -> RoleCode:
        try:
            return RoleCode(account.role.code)
        except (AttributeError, ValueError) as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff is not available for this role") from exc

    async def allowed_association_ids(self, account: Account, *, manage: bool = False) -> list[str] | None:
        role = self.role(account)
        allowed_roles = STAFF_MANAGER_ROLES if manage else STAFF_OPERATOR_ROLES
        if role not in allowed_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff access is required")
        if role == RoleCode.SUPER_ADMIN:
            return None
        return await self.repository.association_ids_for_account(account.id)

    async def require_association_access(self, account: Account, association_id: str, *, manage: bool) -> None:
        allowed = await self.allowed_association_ids(account, manage=manage)
        if not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Association not found")
        if allowed is not None and association_id not in allowed:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Association not found")

    async def list(self, account: Account) -> list[dict]:
        return await self.repository.list_staff(await self.allowed_association_ids(account))

    async def history(self, account: Account) -> list[dict]:
        return await self.repository.attendance_history(await self.allowed_association_ids(account))

    async def blocks(self, association_id: str, account: Account) -> list[dict]:
        await self.require_association_access(account, association_id, manage=True)
        return await self.repository.blocks(association_id)

    async def units(self, block_id: str, account: Account) -> list[dict]:
        allowed = await self.allowed_association_ids(account, manage=True)
        association_id = await self.repository.block_association_id(block_id)
        if association_id is None or (allowed is not None and association_id not in allowed):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Block not found")
        return await self.repository.units(block_id)

    async def create(self, payload: StaffCreateRequest, account: Account) -> tuple[str, str]:
        await self.require_association_access(account, payload.association_id, manage=True)
        if not await self.repository.city_exists(payload.city_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected city was not found")
        await self._validate_assignment(payload)
        email = normalize_email(str(payload.email))
        if await self.repository.account_email_exists(email):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email address is already in use")
        role = await self.repository.staff_role()
        if role is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Staff login role is not configured")
        temporary_password = generate_access_code()
        staff = StaffMember(
            association_id=payload.association_id,
            staff_code=await self._unique_code("STF", self.repository.staff_code_exists),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            designation=payload.designation.strip(),
            contact_number=payload.contact_number,
            email=email,
            assignment_type=payload.assignment_type,
            block_id=payload.block_id,
            unit_id=payload.unit_id,
            address_line_1=payload.address_line_1,
            address_line_2=payload.address_line_2,
            city_id=payload.city_id,
            pincode=payload.pincode,
            emergency_contact_name=payload.emergency_contact_name,
            emergency_contact_number=payload.emergency_contact_number,
            id_proof_url=payload.id_proof_url,
            profile_pic_url=payload.profile_pic_url,
            temp_password=temporary_password,
            pass_code=await self._unique_code("", self.repository.pass_code_exists),
        )
        await self.repository.add_staff(staff)
        login_account = Account(
            email=email,
            password_hash=hash_password(temporary_password),
            role_id=role.id,
        )
        self.repository.session.add(login_account)
        await self.repository.session.flush()
        staff.account_id = login_account.id
        await self.repository.session.flush()
        return staff.id, temporary_password

    async def update(self, staff_id: str, payload: StaffUpdateRequest, account: Account) -> str | None:
        allowed = await self.allowed_association_ids(account, manage=True)
        staff = await self.repository.get_staff(staff_id, allowed)
        if staff is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff member not found")
        await self.require_association_access(account, payload.association_id, manage=True)
        if not await self.repository.city_exists(payload.city_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected city was not found")
        await self._validate_assignment(payload)
        email = normalize_email(str(payload.email))
        if await self.repository.account_email_exists(email, exclude_account_id=staff.get("account_id")):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email address is already in use")
        temporary_password: str | None = None
        account_id = staff.get("account_id")
        if account_id:
            login_account = await self.repository.session.get(Account, account_id)
            if login_account is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "Staff login account was not found")
            login_account.email = email
        else:
            role = await self.repository.staff_role()
            if role is None:
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Staff login role is not configured")
            temporary_password = generate_access_code()
            login_account = Account(email=email, password_hash=hash_password(temporary_password), role_id=role.id)
            self.repository.session.add(login_account)
            await self.repository.session.flush()
            account_id = login_account.id
        await self.repository.update_staff(
            staff_id,
            {
                "association_id": payload.association_id,
                "first_name": payload.first_name.strip(),
                "last_name": payload.last_name.strip(),
                "designation": payload.designation.strip(),
                "contact_number": payload.contact_number,
                "email": email,
                "assignment_type": payload.assignment_type,
                "block_id": payload.block_id,
                "unit_id": payload.unit_id,
                "account_id": account_id,
                **({"temp_password": temporary_password} if temporary_password else {}),
                "address_line_1": payload.address_line_1,
                "address_line_2": payload.address_line_2,
                "city_id": payload.city_id,
                "pincode": payload.pincode,
                "emergency_contact_name": payload.emergency_contact_name,
                "emergency_contact_number": payload.emergency_contact_number,
                "id_proof_url": payload.id_proof_url,
                "profile_pic_url": payload.profile_pic_url,
                "is_active": payload.is_active,
            },
        )
        return temporary_password

    async def _validate_assignment(self, payload: StaffCreateRequest | StaffUpdateRequest) -> None:
        if payload.assignment_type != "unit":
            return
        if not payload.block_id or not await self.repository.block_belongs_to_association(payload.block_id, payload.association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected block does not belong to the association")
        if not payload.unit_id or not await self.repository.unit_belongs_to_block(payload.unit_id, payload.block_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected unit does not belong to the selected block")

    async def toggle_attendance(
        self, pass_code: str, account: Account, *, gate: str | None, remarks: str | None
    ) -> tuple[str, dict]:
        allowed = await self.allowed_association_ids(account)
        normalized = self._pass_code_from_scan(pass_code)
        staff = await self.repository.get_staff_by_pass(normalized, allowed)
        if staff is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Active staff pass not found")
        active = await self.repository.active_attendance(staff["id"])
        if active:
            return "checked_out", await self.repository.close_attendance(
                attendance=active, staff=staff, account_id=account.id, gate=gate, remarks=remarks
            )
        return "checked_in", await self.repository.create_attendance(
            staff=staff, account_id=account.id, gate=gate, remarks=remarks
        )

    async def record_past_attendance(
        self, payload: StaffPastAttendanceRequest, account: Account
    ) -> dict:
        allowed = await self.allowed_association_ids(account, manage=True)
        staff = await self.repository.get_staff(payload.staff_id, allowed)
        if staff is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff member not found")
        if await self.repository.attendance_exists_for_date(staff["id"], payload.check_in_at):
            raise HTTPException(status.HTTP_409_CONFLICT, "Attendance is already recorded for this staff member on that date")
        return await self.repository.create_past_attendance(
            staff=staff,
            account_id=account.id,
            check_in_at=payload.check_in_at,
            check_out_at=payload.check_out_at,
            gate=payload.gate,
            remarks=payload.remarks,
        )

    async def monthly_report(
        self,
        *,
        association_id: str,
        month: str,
        staff_id: str | None,
        designation: str | None,
        account: Account,
    ) -> dict:
        await self.require_association_access(account, association_id, manage=True)
        try:
            year, month_number = (int(value) for value in month.split("-", maxsplit=1))
            start_at = datetime(year, month_number, 1)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Month must use YYYY-MM format") from exc
        if not 1 <= month_number <= 12:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Month must use YYYY-MM format")
        days_in_month = monthrange(year, month_number)[1]
        end_at = datetime(year + (month_number == 12), 1 if month_number == 12 else month_number + 1, 1)
        staff = await self.repository.monthly_staff(association_id, staff_id=staff_id, designation=designation)
        attendance_by_staff: dict[str, dict[str, dict]] = {}
        for entry in await self.repository.monthly_attendance(association_id, start_at, end_at):
            day = entry["check_in_at"].date().isoformat()
            attendance_by_staff.setdefault(entry["staff_id"], {})[day] = entry

        total_present = total_incomplete = total_minutes = 0
        rows: list[dict] = []
        for member in staff:
            present_days = incomplete_days = member_minutes = 0
            days: list[dict] = []
            entries = attendance_by_staff.get(member["id"], {})
            for day_number in range(1, days_in_month + 1):
                day = datetime(year, month_number, day_number).date().isoformat()
                entry = entries.get(day)
                if entry is None:
                    days.append({"date": day, "status": "absent"})
                    continue
                if entry["check_out_at"] is None:
                    incomplete_days += 1
                    days.append({"date": day, "status": "incomplete", "check_in_at": entry["check_in_at"]})
                    continue
                minutes = max(0, int((entry["check_out_at"] - entry["check_in_at"]).total_seconds() // 60))
                present_days += 1
                member_minutes += minutes
                days.append({
                    "date": day,
                    "status": "present",
                    "check_in_at": entry["check_in_at"],
                    "check_out_at": entry["check_out_at"],
                    "duration_minutes": minutes,
                })
            total_present += present_days
            total_incomplete += incomplete_days
            total_minutes += member_minutes
            rows.append({
                "staff_id": member["id"],
                "staff_code": member["staff_code"],
                "staff_name": f"{member['first_name']} {member['last_name']}",
                "designation": member["designation"],
                "days": days,
                "present_days": present_days,
                "incomplete_days": incomplete_days,
                "total_minutes": member_minutes,
                "average_minutes": member_minutes // present_days if present_days else 0,
            })
        return {
            "association_id": association_id,
            "month": month,
            "total_staff": len(rows),
            "present_days": total_present,
            "incomplete_days": total_incomplete,
            "total_minutes": total_minutes,
            "rows": rows,
        }

    @staticmethod
    async def _unique_code(prefix: str, exists) -> str:
        for _ in range(10):
            code = f"{prefix}-{generate_access_code()}" if prefix else generate_access_code()
            if not await exists(code):
                return code
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Unable to generate a unique staff pass")

    @staticmethod
    def _pass_code_from_scan(value: str) -> str:
        """Accept the permanent code itself or the Staff QR URL containing it."""
        parsed = urlparse(value.strip())
        candidate = parse_qs(parsed.query).get("pass", [parsed.path.rsplit("/", 1)[-1]])[0].upper()
        try:
            return normalize_access_code(candidate)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid staff pass") from exc
