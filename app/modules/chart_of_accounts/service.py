"""Chart of Accounts authorization and workflows."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.chart_of_accounts.repository import ChartOfAccountsRepository
from app.modules.chart_of_accounts.schemas import ChartOfAccountRequest


MANAGER_ROLES = {RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT}


class ChartOfAccountsService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ChartOfAccountsRepository(session)

    async def _check_association(self, account, role_code: RoleCode, association_id: str) -> None:
        role_code = RoleCode(role_code)
        if not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Association not found")
        scoped = await self.repository.scoped_associations(account.id, role_code.value, account.user_id)
        if scoped is not None and association_id not in scoped:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized for this association")

    async def global_accounts(self) -> list[dict]:
        return await self.repository.list_global()

    async def status(self, account, role_code: RoleCode) -> dict[str, int]:
        role_code = RoleCode(role_code)
        values = await self.repository.status()
        scoped = await self.repository.scoped_associations(account.id, role_code.value, account.user_id)
        return values if scoped is None else {association_id: count for association_id, count in values.items() if association_id in scoped}

    async def upload_global(self, workbook, account, role_code: RoleCode) -> int:
        role_code = RoleCode(role_code)
        if role_code not in MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only finance managers can import the global Chart of Accounts")
        sheet = workbook.active
        headers = [str(cell.value).strip().lower().replace(" ", "_") if cell.value else "" for cell in sheet[1]]
        indexes = {name: headers.index(name) if name in headers else fallback for name, fallback in {"gl_code": 0, "gl_name": 1, "structure": 2, "grouping": 3}.items()}
        count = 0
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if len(row) <= max(indexes["gl_code"], indexes["gl_name"]) or not row[indexes["gl_code"]] or not row[indexes["gl_name"]]:
                continue
            code = str(row[indexes["gl_code"]]).removesuffix(".0")
            await self.repository.insert_global({"id": str(uuid.uuid4()), "gl_code": code, "gl_name": str(row[indexes["gl_name"]]), "structure": str(row[indexes["structure"]] or ""), "grouping": str(row[indexes["grouping"]] or "")})
            count += 1
        return count

    async def association_accounts(self, account, role_code: RoleCode, association_id: str) -> list[dict]:
        role_code = RoleCode(role_code)
        await self._check_association(account, role_code, association_id)
        return await self.repository.list_association(association_id)

    async def map_global(self, account, role_code: RoleCode, association_id: str) -> int:
        role_code = RoleCode(role_code)
        await self._check_association(account, role_code, association_id)
        if await self.repository.has_association_rows(association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Chart of Accounts is already mapped for this association")
        global_accounts = await self.repository.list_global()
        if not global_accounts:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Global Chart of Accounts is empty")
        for row in global_accounts:
            await self.repository.insert_association({"id": str(uuid.uuid4()), "association_id": association_id, "gl_code": row["gl_code"], "gl_name": row["gl_name"], "structure": row.get("structure"), "grouping": row.get("grouping"), "mapped_from_global_id": row["id"]})
        return len(global_accounts)

    async def add_association(self, account, role_code: RoleCode, association_id: str, payload: ChartOfAccountRequest) -> str:
        role_code = RoleCode(role_code)
        await self._check_association(account, role_code, association_id)
        if await self.repository.duplicate_code(association_id, payload.gl_code):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "GL Code already exists for this association")
        account_id = str(uuid.uuid4())
        await self.repository.insert_association({"id": account_id, "association_id": association_id, **payload.model_dump(), "mapped_from_global_id": None})
        return account_id

    async def update_association(self, account, role_code: RoleCode, account_id: str, payload: ChartOfAccountRequest) -> None:
        role_code = RoleCode(role_code)
        row = await self.repository.get_association_account(account_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Chart of Account not found")
        await self._check_association(account, role_code, row["association_id"])
        if await self.repository.duplicate_code(row["association_id"], payload.gl_code, account_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "GL Code already exists for this association")
        await self.repository.update_association({"id": account_id, **payload.model_dump()})

    async def delete_association(self, account, role_code: RoleCode, account_id: str) -> None:
        role_code = RoleCode(role_code)
        row = await self.repository.get_association_account(account_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Chart of Account not found")
        await self._check_association(account, role_code, row["association_id"])
        await self.repository.delete_association(account_id)
