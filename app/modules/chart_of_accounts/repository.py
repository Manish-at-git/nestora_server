"""SQL access for global and association Chart of Accounts."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode


class ChartOfAccountsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def scoped_associations(self, account_id: str, role_code: str, user_id: str | None) -> list[str] | None:
        if role_code == RoleCode.SUPER_ADMIN.value:
            return None
        rows = await self.session.scalars(
            text("SELECT association_id FROM admin_associations WHERE admin_id=:account_id"),
            {"account_id": account_id},
        )
        values = list(rows.all())
        if values:
            return values
        if user_id:
            association_id = await self.session.scalar(
                text("SELECT association_id FROM user_details WHERE user_id=:user_id AND is_deleted=0 LIMIT 1"),
                {"user_id": user_id},
            )
            if association_id:
                return [association_id]
        return []

    async def list_global(self) -> list[dict]:
        result = await self.session.execute(text("SELECT * FROM global_chart_of_accounts WHERE is_deleted=0 ORDER BY `grouping`, gl_code"))
        return [dict(row) for row in result.mappings().all()]

    async def insert_global(self, values: dict) -> None:
        await self.session.execute(
            text("INSERT INTO global_chart_of_accounts (id,gl_code,gl_name,structure,`grouping`,is_deleted) VALUES (:id,:gl_code,:gl_name,:structure,:grouping,0)"), values
        )

    async def list_association(self, association_id: str) -> list[dict]:
        result = await self.session.execute(
            text("SELECT * FROM association_chart_of_accounts WHERE association_id=:association_id AND is_deleted=0 ORDER BY `grouping`, gl_code"),
            {"association_id": association_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def association_exists(self, association_id: str) -> bool:
        return bool(await self.session.scalar(text("SELECT id FROM associations WHERE id=:id AND is_deleted=0"), {"id": association_id}))

    async def has_association_rows(self, association_id: str) -> bool:
        return bool(await self.session.scalar(text("SELECT id FROM association_chart_of_accounts WHERE association_id=:id AND is_deleted=0 LIMIT 1"), {"id": association_id}))

    async def insert_association(self, values: dict) -> None:
        await self.session.execute(
            text("INSERT INTO association_chart_of_accounts (id,association_id,gl_code,gl_name,structure,`grouping`,mapped_from_global_id,is_deleted) VALUES (:id,:association_id,:gl_code,:gl_name,:structure,:grouping,:mapped_from_global_id,0)"), values
        )

    async def get_association_account(self, account_id: str) -> dict | None:
        result = await self.session.execute(text("SELECT * FROM association_chart_of_accounts WHERE id=:id AND is_deleted=0"), {"id": account_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def duplicate_code(self, association_id: str, gl_code: str, account_id: str | None = None) -> bool:
        query = "SELECT id FROM association_chart_of_accounts WHERE association_id=:association_id AND gl_code=:gl_code AND is_deleted=0"
        params = {"association_id": association_id, "gl_code": gl_code}
        if account_id:
            query += " AND id<>:id"
            params["id"] = account_id
        return bool(await self.session.scalar(text(query), params))

    async def update_association(self, values: dict) -> bool:
        result = await self.session.execute(
            text("UPDATE association_chart_of_accounts SET gl_code=:gl_code,gl_name=:gl_name,structure=:structure,`grouping`=:grouping WHERE id=:id AND is_deleted=0"), values
        )
        return bool(result.rowcount)

    async def delete_association(self, account_id: str) -> bool:
        result = await self.session.execute(text("UPDATE association_chart_of_accounts SET is_deleted=1 WHERE id=:id AND is_deleted=0"), {"id": account_id})
        return bool(result.rowcount)

    async def status(self) -> dict[str, int]:
        result = await self.session.execute(text("SELECT association_id,COUNT(*) count FROM association_chart_of_accounts WHERE is_deleted=0 GROUP BY association_id"))
        return {str(row["association_id"]): int(row["count"]) for row in result.mappings().all()}
