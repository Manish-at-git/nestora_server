"""Database access and association scope checks for bank accounts."""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.bank.models import BankAccount


class BankRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, account_id: str, role_code: str, association_id: str | None = None
    ) -> list[BankAccount]:
        statement = (
            select(BankAccount)
            .options(selectinload(BankAccount.association))
            .join(Association, Association.id == BankAccount.association_id)
            .where(BankAccount.is_deleted.is_(False), Association.is_deleted.is_(False))
            .order_by(BankAccount.created_at.desc())
        )
        if association_id:
            statement = statement.where(BankAccount.association_id == association_id)
        if role_code != RoleCode.SUPER_ADMIN:
            # Keep the legacy association-scope table query explicit because it
            # is not part of the clean IAM ORM model yet.
            scoped_ids = (
                select(text("association_id"))
                .select_from(text("admin_associations"))
                .where(text("admin_id = :account_id"))
                .params(account_id=account_id)
            )
            statement = statement.where(BankAccount.association_id.in_(scoped_ids))
        return list((await self.session.scalars(statement)).all())

    async def get(self, account_id: str, role_code: str, bank_id: str) -> BankAccount | None:
        rows = await self.list(account_id, role_code)
        return next((row for row in rows if row.id == bank_id), None)

    async def association_exists(self, association_id: str) -> bool:
        return await self.session.scalar(
            select(Association.id).where(
                Association.id == association_id,
                Association.is_deleted.is_(False),
            )
        ) is not None

    async def can_access_association(self, account_id: str, role_code: str, association_id: str) -> bool:
        if role_code == RoleCode.SUPER_ADMIN:
            return await self.association_exists(association_id)
        result = await self.session.execute(
            text(
                "SELECT 1 FROM admin_associations WHERE admin_id = :account_id "
                "AND association_id = :association_id LIMIT 1"
            ),
            {"account_id": account_id, "association_id": association_id},
        )
        return result.first() is not None and await self.association_exists(association_id)

    def add(self, account: BankAccount) -> None:
        self.session.add(account)
