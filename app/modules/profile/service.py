"""Profile use cases and ownership rules."""

from fastapi import HTTPException, status

from app.modules.auth.models import Account
from app.modules.profile.repository import ProfileRepository


class ProfileService:
    def __init__(self, repository: ProfileRepository) -> None:
        self.repository = repository

    async def data(self, account: Account) -> dict:
        return await self.repository.profile_data(account)

    async def update_details(self, account: Account, payload) -> None:
        if not account.user_id and not account.employee_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Profile updates are not available for this account.")
        await self.repository.update_details(account, payload.model_dump(exclude_unset=True))

    async def family_member(self, account: Account, payload) -> str:
        if not account.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only members can add family members.")
        return await self.repository.insert("family_members", {"user_id": account.user_id, **payload.model_dump()})

    async def member_record(self, table: str, account: Account, payload, record_id: str | None = None) -> str | None:
        if not account.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only members can manage this profile record.")
        values = payload.model_dump()
        if record_id:
            await self.repository.update_record(table, record_id, values, account)
            return record_id
        return await self.repository.insert(table, {"user_id": account.user_id, **values})

    async def employee_record(self, table: str, account: Account, payload, record_id: str | None = None) -> str | None:
        if not account.employee_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only employees can manage this profile record.")
        values = payload.model_dump()
        if record_id:
            await self.repository.update_record(table, record_id, values, account, employee=True)
            return record_id
        return await self.repository.insert(table, {"employee_id": account.employee_id, **values})

    async def delete_member_record(self, table: str, account: Account, record_id: str) -> None:
        if not account.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only members can delete this profile record.")
        await self.repository.delete_record(table, record_id, account)

    async def delete_employee_record(self, table: str, account: Account, record_id: str) -> None:
        if not account.employee_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only employees can delete this profile record.")
        await self.repository.delete_record(table, record_id, account, employee=True)
