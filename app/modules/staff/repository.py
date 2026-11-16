"""Database queries for association staff and QR attendance."""

import uuid

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.associations.models import Association
from app.modules.auth.models import Account
from app.modules.iam.models import Role
from app.modules.locations.models import City, Region
from app.modules.staff.models import StaffAttendance, StaffMember


class StaffRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def association_ids_for_account(self, account_id: str) -> list[str]:
        result = await self.session.scalars(
            text("SELECT association_id FROM admin_associations WHERE admin_id = :account_id"),
            {"account_id": account_id},
        )
        return list(result.all())

    async def association_exists(self, association_id: str) -> bool:
        return bool(
            await self.session.scalar(
                select(Association.id).where(
                    Association.id == association_id,
                    Association.is_deleted.is_(False),
                    Association.is_active.is_(True),
                )
            )
        )

    async def staff_code_exists(self, code: str) -> bool:
        return bool(await self.session.scalar(select(StaffMember.id).where(StaffMember.staff_code == code)))

    async def pass_code_exists(self, code: str) -> bool:
        return bool(await self.session.scalar(select(StaffMember.id).where(StaffMember.pass_code == code)))

    async def city_exists(self, city_id: str) -> bool:
        return bool(await self.session.scalar(select(City.id).where(City.id == city_id)))

    async def block_belongs_to_association(self, block_id: str, association_id: str) -> bool:
        return bool(await self.session.scalar(
            text("SELECT id FROM blocks WHERE id=:block_id AND association_id=:association_id LIMIT 1"),
            {"block_id": block_id, "association_id": association_id},
        ))

    async def block_association_id(self, block_id: str) -> str | None:
        return await self.session.scalar(
            text("SELECT association_id FROM blocks WHERE id=:block_id LIMIT 1"), {"block_id": block_id}
        )

    async def unit_belongs_to_block(self, unit_id: str, block_id: str) -> bool:
        return bool(await self.session.scalar(
            text("SELECT id FROM units WHERE id=:unit_id AND block_id=:block_id LIMIT 1"),
            {"unit_id": unit_id, "block_id": block_id},
        ))

    async def blocks(self, association_id: str) -> list[dict]:
        rows = await self.session.execute(
            text("SELECT id,name FROM blocks WHERE association_id=:association_id ORDER BY name"),
            {"association_id": association_id},
        )
        return [dict(row) for row in rows.mappings().all()]

    async def units(self, block_id: str) -> list[dict]:
        rows = await self.session.execute(
            text("SELECT id,unit_number FROM units WHERE block_id=:block_id ORDER BY unit_number"),
            {"block_id": block_id},
        )
        return [dict(row) for row in rows.mappings().all()]

    async def account_email_exists(self, email: str, *, exclude_account_id: str | None = None) -> bool:
        statement = select(Account.id).where(func.lower(Account.email) == email.lower())
        if exclude_account_id:
            statement = statement.where(Account.id != exclude_account_id)
        return bool(await self.session.scalar(statement))

    async def staff_role(self) -> Role | None:
        return await self.session.scalar(
            select(Role).where(Role.code == "staff", Role.is_active.is_(True), Role.is_deleted.is_(False))
        )

    async def list_staff(self, association_ids: list[str] | None) -> list[dict]:
        if association_ids is not None and not association_ids:
            return []
        query = (
            "SELECT s.id,s.association_id,a.name association_name,s.staff_code,s.first_name,s.last_name,"
            "s.designation,s.contact_number,s.email,s.assignment_type,s.block_id,b.name block_name,s.unit_id,u.unit_number,"
            "s.account_id,s.temp_password,s.address_line_1,s.address_line_2,s.city_id,"
            "city.name city,region.id region_id,region.name state,region.country_id,s.pincode,"
            "s.emergency_contact_name,s.emergency_contact_number,s.id_proof_url,s.profile_pic_url,s.pass_code,"
            "s.is_active,s.created_at,"
            "(SELECT sa.id FROM staff_attendance sa WHERE sa.staff_id=s.id "
            "AND sa.check_out_at IS NULL AND sa.is_deleted=0 ORDER BY sa.check_in_at DESC LIMIT 1) active_attendance_id,"
            "(SELECT sa.check_out_at FROM staff_attendance sa WHERE sa.staff_id=s.id "
            "AND sa.check_out_at IS NOT NULL AND sa.is_deleted=0 AND DATE(sa.check_in_at)=CURRENT_DATE "
            "ORDER BY sa.check_out_at DESC LIMIT 1) today_check_out_at "
            "FROM staff_members s JOIN associations a ON a.id=s.association_id "
            "LEFT JOIN blocks b ON b.id=s.block_id "
            "LEFT JOIN units u ON u.id=s.unit_id "
            "LEFT JOIN location_cities city ON city.id=s.city_id "
            "LEFT JOIN location_regions region ON region.id=city.region_id "
            "WHERE s.is_deleted=0 AND a.is_deleted=0"
        )
        params: dict = {}
        if association_ids is not None:
            query += " AND s.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        query += " ORDER BY a.name,s.first_name,s.last_name"
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        rows = await self.session.execute(statement, params)
        return [dict(row) for row in rows.mappings().all()]

    async def get_staff(self, staff_id: str, association_ids: list[str] | None = None) -> dict | None:
        if association_ids is not None and not association_ids:
            return None
        query = (
            "SELECT s.*,a.name association_name FROM staff_members s "
            "JOIN associations a ON a.id=s.association_id "
            "WHERE s.id=:staff_id AND s.is_deleted=0 AND a.is_deleted=0"
        )
        params: dict = {"staff_id": staff_id}
        if association_ids is not None:
            query += " AND s.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        row = await self.session.execute(statement, params)
        value = row.mappings().first()
        return dict(value) if value else None

    async def get_staff_by_pass(self, pass_code: str, association_ids: list[str] | None) -> dict | None:
        if association_ids is not None and not association_ids:
            return None
        query = (
            "SELECT s.*,a.name association_name FROM staff_members s "
            "JOIN associations a ON a.id=s.association_id "
            "WHERE s.pass_code=:pass_code AND s.is_deleted=0 AND s.is_active=1 AND a.is_deleted=0"
        )
        params: dict = {"pass_code": pass_code}
        if association_ids is not None:
            query += " AND s.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        # The surrounding UnitOfWork locks this row before checking its open
        # attendance, serializing near-simultaneous scans of the same pass.
        query += " FOR UPDATE"
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        row = await self.session.execute(statement, params)
        value = row.mappings().first()
        return dict(value) if value else None

    async def add_staff(self, staff: StaffMember) -> None:
        self.session.add(staff)
        await self.session.flush()

    async def update_staff(self, staff_id: str, values: dict) -> None:
        fields = ",".join(f"{field}=:{field}" for field in values)
        await self.session.execute(
            text(f"UPDATE staff_members SET {fields} WHERE id=:id AND is_deleted=0"),
            {**values, "id": staff_id},
        )

    async def active_attendance(self, staff_id: str) -> dict | None:
        row = await self.session.execute(
            text(
                "SELECT * FROM staff_attendance WHERE staff_id=:staff_id AND check_out_at IS NULL "
                "AND is_deleted=0 ORDER BY check_in_at DESC LIMIT 1"
            ),
            {"staff_id": staff_id},
        )
        value = row.mappings().first()
        return dict(value) if value else None

    async def attendance_exists_for_date(self, staff_id: str, check_in_at) -> bool:
        return bool(await self.session.scalar(
            text(
                "SELECT id FROM staff_attendance WHERE staff_id=:staff_id AND is_deleted=0 "
                "AND DATE(check_in_at)=DATE(:check_in_at) LIMIT 1"
            ),
            {"staff_id": staff_id, "check_in_at": check_in_at},
        ))

    async def create_attendance(self, *, staff: dict, account_id: str, gate: str | None, remarks: str | None) -> dict:
        attendance = StaffAttendance(
            id=str(uuid.uuid4()),
            staff_id=staff["id"],
            association_id=staff["association_id"],
            checked_in_by=account_id,
            gate=gate,
            remarks=remarks,
        )
        self.session.add(attendance)
        await self.session.flush()
        await self.session.refresh(attendance)
        return {
            "id": attendance.id,
            "staff_id": staff["id"],
            "staff_name": f"{staff['first_name']} {staff['last_name']}",
            "staff_code": staff["staff_code"],
            "designation": staff["designation"],
            "association_id": staff["association_id"],
            "association_name": staff["association_name"],
            "check_in_at": attendance.check_in_at,
            "check_out_at": None,
            "gate": attendance.gate,
            "remarks": attendance.remarks,
        }

    async def create_past_attendance(
        self, *, staff: dict, account_id: str, check_in_at, check_out_at, gate: str | None, remarks: str | None
    ) -> dict:
        attendance = StaffAttendance(
            id=str(uuid.uuid4()),
            staff_id=staff["id"],
            association_id=staff["association_id"],
            check_in_at=check_in_at,
            check_out_at=check_out_at,
            checked_in_by=account_id,
            checked_out_by=account_id,
            gate=gate,
            remarks=remarks,
        )
        self.session.add(attendance)
        await self.session.flush()
        return {
            "id": attendance.id,
            "staff_id": staff["id"],
            "staff_name": f"{staff['first_name']} {staff['last_name']}",
            "staff_code": staff["staff_code"],
            "designation": staff["designation"],
            "association_id": staff["association_id"],
            "association_name": staff["association_name"],
            "check_in_at": attendance.check_in_at,
            "check_out_at": attendance.check_out_at,
            "gate": attendance.gate,
            "remarks": attendance.remarks,
        }

    async def close_attendance(self, *, attendance: dict, staff: dict, account_id: str, gate: str | None, remarks: str | None) -> dict:
        await self.session.execute(
            text(
                "UPDATE staff_attendance SET check_out_at=CURRENT_TIMESTAMP,checked_out_by=:account_id,"
                "gate=COALESCE(:gate,gate),remarks=COALESCE(:remarks,remarks) "
                "WHERE id=:id AND check_out_at IS NULL AND is_deleted=0"
            ),
            {"id": attendance["id"], "account_id": account_id, "gate": gate, "remarks": remarks},
        )
        row = await self.session.execute(
            text("SELECT check_in_at,check_out_at,gate,remarks FROM staff_attendance WHERE id=:id"),
            {"id": attendance["id"]},
        )
        updated = dict(row.mappings().one())
        return {
            "id": attendance["id"],
            "staff_id": staff["id"],
            "staff_name": f"{staff['first_name']} {staff['last_name']}",
            "staff_code": staff["staff_code"],
            "designation": staff["designation"],
            "association_id": staff["association_id"],
            "association_name": staff["association_name"],
            **updated,
        }

    async def attendance_history(self, association_ids: list[str] | None) -> list[dict]:
        if association_ids is not None and not association_ids:
            return []
        query = (
            "SELECT sa.id,sa.staff_id,CONCAT(s.first_name,' ',s.last_name) staff_name,s.staff_code,"
            "s.designation,sa.association_id,a.name association_name,sa.check_in_at,sa.check_out_at,sa.gate,sa.remarks "
            "FROM staff_attendance sa JOIN staff_members s ON s.id=sa.staff_id "
            "JOIN associations a ON a.id=sa.association_id "
            "WHERE sa.is_deleted=0 AND s.is_deleted=0 AND a.is_deleted=0"
        )
        params: dict = {}
        if association_ids is not None:
            query += " AND sa.association_id IN :association_ids"
            params["association_ids"] = tuple(association_ids)
        query += " ORDER BY sa.check_in_at DESC LIMIT 200"
        statement = text(query)
        if association_ids is not None:
            statement = statement.bindparams(bindparam("association_ids", expanding=True))
        rows = await self.session.execute(statement, params)
        return [dict(row) for row in rows.mappings().all()]

    async def monthly_staff(
        self, association_id: str, *, staff_id: str | None, designation: str | None
    ) -> list[dict]:
        query = (
            "SELECT id,staff_code,first_name,last_name,designation FROM staff_members "
            "WHERE association_id=:association_id AND is_deleted=0"
        )
        params: dict = {"association_id": association_id}
        if staff_id:
            query += " AND id=:staff_id"
            params["staff_id"] = staff_id
        if designation:
            query += " AND designation=:designation"
            params["designation"] = designation
        query += " ORDER BY first_name,last_name"
        rows = await self.session.execute(text(query), params)
        return [dict(row) for row in rows.mappings().all()]

    async def monthly_attendance(self, association_id: str, start_at, end_at) -> list[dict]:
        rows = await self.session.execute(
            text(
                "SELECT staff_id,check_in_at,check_out_at FROM staff_attendance "
                "WHERE association_id=:association_id AND is_deleted=0 "
                "AND check_in_at>=:start_at AND check_in_at<:end_at ORDER BY check_in_at"
            ),
            {"association_id": association_id, "start_at": start_at, "end_at": end_at},
        )
        return [dict(row) for row in rows.mappings().all()]
