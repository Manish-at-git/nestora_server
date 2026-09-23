"""Persistence and association-scope queries for employees."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contact_normalization import normalize_email, normalize_phone
from app.modules.associations.models import Association
from app.modules.auth.models import Account
from app.modules.employees.models import Employee
from app.modules.iam.models import Role
from app.modules.users.models import UserDetail


class EmployeeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def email_exists(self, email: str) -> bool:
        target = normalize_email(email)
        users = await self.session.scalars(select(UserDetail).where(UserDetail.is_deleted.is_(False)))
        if any(normalize_email(user.email) == target for user in users.all()):
            return True
        employees = await self.session.scalars(
            select(Employee).where(Employee.is_deleted.is_(False))
        )
        if any(normalize_email(employee.email) == target for employee in employees.all()):
            return True
        accounts = await self.session.scalars(select(Account))
        return any(normalize_email(account.email) == target for account in accounts.all())

    async def phone_exists(self, phone: str) -> bool:
        target = normalize_phone(phone)
        if not target:
            return False
        users = await self.session.scalars(select(UserDetail).where(UserDetail.is_deleted.is_(False)))
        if any(normalize_phone(user.contact_number) == target for user in users.all()):
            return True
        employees = await self.session.scalars(
            select(Employee).where(Employee.is_deleted.is_(False))
        )
        return any(normalize_phone(employee.contact_number) == target for employee in employees.all())

    async def role(self, role_id: str) -> Role | None:
        return await self.session.scalar(
            select(Role).where(Role.id == role_id, Role.is_active.is_(True), Role.is_deleted.is_(False))
        )

    async def associations_exist(self, association_ids: list[str]) -> bool:
        if not association_ids:
            return True
        rows = await self.session.scalars(
            select(Association.id).where(
                Association.id.in_(association_ids),
                Association.is_deleted.is_(False),
            )
        )
        return len(set(rows.all())) == len(set(association_ids))

    async def next_employee_number(self, role_name: str) -> str:
        prefix = f"NT{role_name[:2].upper()}#"
        result = await self.session.execute(
            text(
                "SELECT employee_id_number FROM employees "
                "WHERE employee_id_number LIKE :prefix "
                "ORDER BY LENGTH(employee_id_number) DESC, employee_id_number DESC LIMIT 1"
            ),
            {"prefix": f"{prefix}%"},
        )
        row = result.first()
        try:
            next_number = int(row[0].split("#", 1)[1]) + 1 if row else 1
        except (ValueError, IndexError):
            next_number = 1
        return f"{prefix}{next_number}"

    async def list(self) -> list[dict]:
        rows = (
            await self.session.execute(
                select(Account, Employee, Role)
                .join(Employee, Account.employee_id == Employee.employee_id)
                .join(Role, Account.role_id == Role.id)
                .where(Employee.is_deleted.is_(False), Role.is_deleted.is_(False))
                .order_by(Account.created_at.desc())
            )
        ).all()
        result = []
        for account, employee, role in rows:
            association_rows = await self.session.execute(
                text(
                    "SELECT a.id, a.name FROM admin_associations aa "
                    "JOIN associations a ON a.id = aa.association_id "
                    "WHERE aa.admin_id = :account_id AND a.is_deleted = 0"
                ),
                {"account_id": account.id},
            )
            result.append(
                {
                    "account": account,
                    "employee": employee,
                    "role": role,
                    "associations": [dict(row) for row in association_rows.mappings().all()],
                }
            )
        return result

    async def get(self, account_id: str) -> dict | None:
        rows = (
            await self.session.execute(
                select(Account, Employee, Role)
                .join(Employee, Account.employee_id == Employee.employee_id)
                .join(Role, Account.role_id == Role.id)
                .where(Account.id == account_id, Employee.is_deleted.is_(False))
            )
        ).first()
        if rows is None:
            return None
        account, employee, role = rows
        association_rows = await self.session.execute(
            text(
                "SELECT a.id, a.name FROM admin_associations aa "
                "JOIN associations a ON a.id = aa.association_id "
                "WHERE aa.admin_id = :account_id AND a.is_deleted = 0"
            ),
            {"account_id": account.id},
        )
        return {
            "account": account,
            "employee": employee,
            "role": role,
            "associations": [dict(row) for row in association_rows.mappings().all()],
        }

    async def replace_associations(self, account_id: str, association_ids: list[str]) -> None:
        await self.session.execute(
            text("DELETE FROM admin_associations WHERE admin_id = :account_id"),
            {"account_id": account_id},
        )
        for association_id in dict.fromkeys(association_ids):
            await self.session.execute(
                text(
                    "INSERT INTO admin_associations (admin_id, association_id) "
                    "VALUES (:account_id, :association_id)"
                ),
                {"account_id": account_id, "association_id": association_id},
            )

    def add_employee(self, employee: Employee) -> None:
        self.session.add(employee)

    def add_account(self, account: Account) -> None:
        self.session.add(account)
