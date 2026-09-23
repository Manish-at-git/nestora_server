"""Persistence boundary for resident/user administration."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_codes import generate_access_code
from app.core.contact_normalization import normalize_email, normalize_phone
from app.modules.associations.models import Association
from app.modules.auth.models import Account
from app.modules.employees.models import Employee
from app.modules.iam.models import Role
from app.modules.users.models import UserCode, UserDetail


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def email_exists(self, email: str, excluding_user_id: str | None = None) -> bool:
        target = normalize_email(email)
        users = await self.session.scalars(
            select(UserDetail).where(UserDetail.is_deleted.is_(False))
        )
        if any(
            user.user_id != excluding_user_id and normalize_email(user.email) == target
            for user in users.all()
        ):
            return True
        employees = await self.session.scalars(
            select(Employee).where(Employee.is_deleted.is_(False))
        )
        if any(normalize_email(employee.email) == target for employee in employees.all()):
            return True
        accounts = await self.session.scalars(select(Account))
        return any(
            account.user_id != excluding_user_id and normalize_email(account.email) == target
            for account in accounts.all()
        )

    async def phone_exists(self, phone: str, excluding_user_id: str | None = None) -> bool:
        target = normalize_phone(phone)
        if not target:
            return False
        users = await self.session.scalars(
            select(UserDetail).where(UserDetail.is_deleted.is_(False))
        )
        if any(
            user.user_id != excluding_user_id and normalize_phone(user.contact_number) == target
            for user in users.all()
        ):
            return True
        employees = await self.session.scalars(
            select(Employee).where(Employee.is_deleted.is_(False))
        )
        return any(normalize_phone(employee.contact_number) == target for employee in employees.all())

    async def role(self, role_id: str | None = None, role_name: str | None = None) -> Role | None:
        statement = select(Role).where(Role.is_active.is_(True), Role.is_deleted.is_(False))
        if role_id:
            statement = statement.where(Role.id == role_id)
        if role_name:
            statement = statement.where(
                (Role.name.ilike(role_name)) | (Role.code.ilike(role_name))
            )
        return await self.session.scalar(statement)

    async def association_exists(self, association_id: str) -> bool:
        return await self.session.scalar(
            select(Association.id).where(
                Association.id == association_id,
                Association.is_deleted.is_(False),
            )
        ) is not None

    async def create_code(self) -> UserCode:
        for _ in range(10):
            candidate = generate_access_code()
            if await self.session.scalar(select(UserCode.id).where(UserCode.login_code == candidate)) is None:
                code = UserCode(id=str(uuid.uuid4()), login_code=candidate, status="active")
                self.session.add(code)
                await self.session.flush()
                return code
        raise RuntimeError("Could not generate a unique activation code")

    async def get(self, user_id: str) -> UserDetail | None:
        return await self.session.scalar(
            select(UserDetail).where(UserDetail.user_id == user_id, UserDetail.is_deleted.is_(False))
        )

    async def list(self) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT u.user_id, u.first_name, u.last_name, u.name, u.contact_number, u.email, "
                "a.account_id, uc.login_code AS activation_code, uc.status AS activation_status, "
                "COALESCE(r.name, '') AS role_name, "
                "un.id AS unit_id, b.id AS block_id, COALESCE(assoc.id, dir_assoc.id) AS association_id, "
                "COALESCE(assoc.name, dir_assoc.name) AS association_name, b.name AS block_name, "
                "un.unit_number, COALESCE(assoc.address_line_1, dir_assoc.address_line_1) AS assoc_addr1, "
                "COALESCE(assoc.address_line_2, dir_assoc.address_line_2) AS assoc_addr2, "
                "COALESCE(assoc.city, dir_assoc.city) AS assoc_city, "
                "COALESCE(assoc.state, dir_assoc.state) AS assoc_state, "
                "COALESCE(assoc.pincode, dir_assoc.pincode) AS assoc_pincode, u.created_at "
                "FROM user_details u LEFT JOIN accounts a ON u.user_id = a.user_id "
                "LEFT JOIN roles r ON COALESCE(a.role_id, u.role_id) = r.id "
                "LEFT JOIN user_codes uc ON u.code_id = uc.id "
                "LEFT JOIN units un ON u.unit_id = un.id "
                "LEFT JOIN blocks b ON un.block_id = b.id "
                "LEFT JOIN associations assoc ON b.association_id = assoc.id "
                "LEFT JOIN associations dir_assoc ON u.association_id = dir_assoc.id "
                "WHERE u.is_deleted = 0 AND (b.association_id IS NOT NULL OR u.association_id IS NOT NULL) "
                "ORDER BY u.created_at DESC"
            )
        )
        return [dict(row) for row in result.mappings().all()]

    async def find_account(self, user_id: str) -> Account | None:
        return await self.session.scalar(select(Account).where(Account.user_id == user_id))

    async def find_unit(self, association_id: str, block_name: str, unit_number: str) -> str | None:
        result = await self.session.execute(
            text(
                "SELECT u.id FROM units u JOIN blocks b ON u.block_id = b.id "
                "WHERE b.association_id = :association_id AND b.name = :block_name "
                "AND u.unit_number = :unit_number LIMIT 1"
            ),
            {
                "association_id": association_id,
                "block_name": block_name,
                "unit_number": unit_number,
            },
        )
        row = result.first()
        return row[0] if row else None

    async def block_exists(self, association_id: str, block_name: str) -> bool:
        result = await self.session.execute(
            text(
                "SELECT id FROM blocks WHERE association_id = :association_id "
                "AND name = :block_name LIMIT 1"
            ),
            {"association_id": association_id, "block_name": block_name},
        )
        return result.first() is not None

    async def update_account_email(self, user_id: str, email: str) -> None:
        account = await self.find_account(user_id)
        if account:
            account.email = email

    def add_user(self, user: UserDetail) -> None:
        self.session.add(user)
