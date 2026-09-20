"""Profile data access; SQL is kept here so routes contain no persistence logic."""

from datetime import date, datetime
from typing import Any
import uuid

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Account


def _serialize(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _one(self, query: str, params: dict[str, Any]) -> dict[str, Any] | None:
        row = (await self.session.execute(text(query), params)).mappings().first()
        return _serialize(dict(row)) if row else None

    async def _many(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        rows = (await self.session.execute(text(query), params)).mappings().all()
        return [_serialize(dict(row)) for row in rows]

    async def profile_data(self, account: Account) -> dict[str, Any]:
        uid, eid = account.user_id, account.employee_id
        details: dict[str, Any] = {}
        family: list[dict[str, Any]] = []
        homeowners: list[dict[str, Any]] = []
        vehicles: list[dict[str, Any]] = []
        pets: list[dict[str, Any]] = []
        education: list[dict[str, Any]] = []
        experience: list[dict[str, Any]] = []

        if eid:
            details = await self._one("SELECT * FROM employees WHERE employee_id = :id AND is_deleted = 0", {"id": eid}) or {}
            education = await self._many("SELECT * FROM employee_education WHERE employee_id = :id ORDER BY created_at DESC", {"id": eid})
            experience = await self._many("SELECT * FROM employee_experience WHERE employee_id = :id ORDER BY created_at DESC", {"id": eid})
        elif uid:
            details = await self._one("SELECT * FROM user_details WHERE user_id = :id AND is_deleted = 0", {"id": uid}) or {}
            family = await self._many("SELECT * FROM family_members WHERE user_id = :id ORDER BY created_at DESC", {"id": uid})
            unit_id = details.get("unit_id")
            if unit_id:
                vehicles = await self._many("SELECT v.* FROM vehicles v JOIN user_details u ON u.user_id = v.user_id WHERE u.unit_id = :unit AND u.is_deleted = 0 ORDER BY v.created_at DESC", {"unit": unit_id})
                pets = await self._many("SELECT p.* FROM pets p JOIN user_details u ON u.user_id = p.user_id WHERE u.unit_id = :unit AND u.is_deleted = 0 ORDER BY p.created_at DESC", {"unit": unit_id})
                homeowners = await self._many("SELECT * FROM user_details WHERE unit_id = :unit AND user_id != :id AND is_deleted = 0", {"unit": unit_id, "id": uid})
            else:
                vehicles = await self._many("SELECT * FROM vehicles WHERE user_id = :id ORDER BY created_at DESC", {"id": uid})
                pets = await self._many("SELECT * FROM pets WHERE user_id = :id ORDER BY created_at DESC", {"id": uid})

        if not details and not (uid or eid):
            details = {"name": "Platform Administrator", "email": account.email, "contact_number": "-", "address": "Global Platform Scope", "profile_pic_url": None}

        association = await self._one(
            """SELECT COALESCE(a.name, direct.name, admin_assoc.name, board_assoc.name) AS association_name,
                      COALESCE(a.id, direct.id, admin_assoc.id, board_assoc.id) AS association_id
               FROM accounts ac
               LEFT JOIN user_details ud ON ac.user_id = ud.user_id
               LEFT JOIN units un ON ud.unit_id = un.id
               LEFT JOIN blocks b ON un.block_id = b.id
               LEFT JOIN associations a ON b.association_id = a.id
               LEFT JOIN associations direct ON ud.association_id = direct.id
               LEFT JOIN admin_associations aa ON aa.admin_id = ac.account_id
               LEFT JOIN associations admin_assoc ON aa.association_id = admin_assoc.id
               LEFT JOIN board_members bm ON bm.account_id = ac.account_id AND bm.status = 'active'
               LEFT JOIN associations board_assoc ON bm.association_id = board_assoc.id
               WHERE ac.account_id = :account_id LIMIT 1""",
            {"account_id": account.id},
        )
        if association:
            details.setdefault("association_name", association.get("association_name"))
            details.setdefault("association_id", association.get("association_id"))
        return {"user_details": details, "family_members": family, "unit_homeowners": homeowners, "vehicles": vehicles, "pets": pets, "education": education, "experience": experience, "association_name": association.get("association_name") if association else None, "association_id": association.get("association_id") if association else None}

    async def update_details(self, account: Account, values: dict[str, Any]) -> None:
        target, key = ("user_details", "user_id") if account.user_id else ("employees", "employee_id")
        values = {key: value for key, value in values.items() if value is not None}
        if not values:
            return
        allowed = {"name", "address", "email", "contact_number", "alt_contact_number", "profile_pic_url"}
        values = {key: value for key, value in values.items() if key in allowed}
        assignments = ", ".join(f"{key} = :{key}" for key in values)
        values["identity"] = account.user_id or account.employee_id
        await self.session.execute(text(f"UPDATE {target} SET {assignments} WHERE {key} = :identity"), values)

    async def insert(self, table: str, values: dict[str, Any]) -> str:
        record_id = str(uuid.uuid4())
        values = {"id": record_id, **values}
        columns = ", ".join(values)
        binds = ", ".join(f":{key}" for key in values)
        await self.session.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({binds})"), values)
        return record_id

    async def owned(self, table: str, record_id: str, account: Account, employee: bool = False) -> bool:
        if employee:
            query = f"SELECT 1 FROM {table} WHERE id = :id AND employee_id = :owner"
            owner = account.employee_id
        else:
            query = f"SELECT 1 FROM {table} WHERE id = :id AND user_id = :owner"
            owner = account.user_id
        if not owner:
            return False
        return await self.session.scalar(text(query), {"id": record_id, "owner": owner}) is not None

    async def update_record(self, table: str, record_id: str, values: dict[str, Any], account: Account, employee: bool = False) -> None:
        if not await self.owned(table, record_id, account, employee):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile record not found.")
        assignments = ", ".join(f"{key} = :{key}" for key in values)
        values = {**values, "id": record_id}
        await self.session.execute(text(f"UPDATE {table} SET {assignments} WHERE id = :id"), values)

    async def delete_record(self, table: str, record_id: str, account: Account, employee: bool = False) -> None:
        if not await self.owned(table, record_id, account, employee):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile record not found.")
        await self.session.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": record_id})
