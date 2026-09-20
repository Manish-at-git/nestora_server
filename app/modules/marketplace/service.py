"""Marketplace authorization and transactional workflows."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.marketplace.repository import MarketplaceRepository
from app.modules.marketplace.schemas import (
    MarketplaceFilters,
    MarketplaceItemRequest,
    MarketplaceItemUpdateRequest,
)


MANAGER_ROLES = {RoleCode.SUPER_ADMIN, RoleCode.ADMIN}
MARKETPLACE_ROLES = tuple(RoleCode)


class MarketplaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = MarketplaceRepository(session)

    @staticmethod
    def role_code(account: Account) -> RoleCode:
        try:
            return RoleCode(account.role.code)
        except (AttributeError, ValueError) as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Marketplace access is not available for this role") from exc

    async def scope(self, account: Account, role: RoleCode) -> list[str] | None:
        if role == RoleCode.SUPER_ADMIN:
            return None
        if role == RoleCode.ADMIN:
            return await self.repository.association_ids_for_admin(account.id)
        return await self.repository.member_association_ids(account.id, account.user_id)

    async def _authorized_item(self, item_id: str, account: Account) -> dict:
        item = await self.repository.get_item(item_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Marketplace item not found")
        # Older listings stored user_details.user_id instead of accounts.account_id.
        item["user_id"] = item.get("owner_account_id") or item["user_id"]
        role = self.role_code(account)
        if role not in MANAGER_ROLES:
            allowed = await self.scope(account, role)
            if allowed is not None and item["association_id"] not in allowed:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        return item

    async def categories(self) -> list[dict]:
        return await self.repository.categories()

    async def list_items(self, account: Account, filters: MarketplaceFilters) -> list[dict]:
        role = self.role_code(account)
        return await self.repository.list_items(account.id, await self.scope(account, role), filters.model_dump())

    async def my_items(self, account: Account) -> list[dict]:
        role = self.role_code(account)
        return await self.repository.list_items(account.id, await self.scope(account, role), {"status": None}, True)

    async def saved_items(self, account: Account) -> list[dict]:
        self.role_code(account)
        return await self.repository.favorites(account.id)

    async def create(self, payload: MarketplaceItemRequest, account: Account) -> str:
        role = self.role_code(account)
        allowed = await self.scope(account, role)
        association_id = payload.association_id
        if association_id is None:
            if allowed:
                association_id = allowed[0]
            elif role == RoleCode.SUPER_ADMIN:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "association_id is required")
            else:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your account is not linked to an association")
        if allowed is not None and association_id not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unauthorized for this association")
        if not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Association not found")
        item_id = str(uuid.uuid4())
        values = payload.model_dump(exclude={"association_id", "images"})
        values.update({"id": item_id, "association_id": association_id, "user_id": account.id})
        return await self.repository.create_item(values, payload.images)

    async def update(self, item_id: str, payload: MarketplaceItemUpdateRequest, account: Account) -> None:
        item = await self._authorized_item(item_id, account)
        role = self.role_code(account)
        if item["user_id"] != account.id and role not in MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        values = payload.model_dump(exclude_unset=True, exclude={"images"})
        if "category_id" in values and values["category_id"] is None:
            values.pop("category_id")
        if not await self.repository.update_item(item_id, values, payload.images):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Marketplace item not found")

    async def delete(self, item_id: str, account: Account) -> None:
        item = await self._authorized_item(item_id, account)
        if item["user_id"] != account.id and self.role_code(account) not in MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        await self.repository.delete_item(item_id)

    async def toggle_favorite(self, item_id: str, account: Account) -> bool:
        await self._authorized_item(item_id, account)
        return await self.repository.toggle_favorite(account.id, item_id)

    async def report(self, item_id: str, reason: str, account: Account) -> str:
        await self._authorized_item(item_id, account)
        return await self.repository.add_report(item_id, account.id, reason)

    async def threads(self, item_id: str, account: Account) -> list[dict]:
        item = await self._authorized_item(item_id, account)
        if item["user_id"] != account.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can view marketplace threads")
        return await self.repository.chat_threads(item_id, account.id)

    async def chat(self, item_id: str, buyer_id: str | None, account: Account) -> list[dict]:
        item = await self._authorized_item(item_id, account)
        if item["user_id"] == account.id:
            if not buyer_id:
                return await self.repository.chat_for_account(item_id, account.id)
            target = buyer_id
        else:
            target = account.id
        return await self.repository.chat(item_id, target, item["user_id"])

    async def send_chat(self, item_id: str, message: str, receiver_id: str | None, account: Account) -> dict:
        item = await self._authorized_item(item_id, account)
        if item["user_id"] == account.id:
            if not receiver_id:
                receiver_id = await self.repository.latest_chat_peer(item_id, account.id)
            if not receiver_id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "receiver_id is required for owner replies")
            target = receiver_id
        else:
            target = item["user_id"]
        if target == account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot message yourself")
        return await self.repository.add_chat(item_id, account.id, target, message)

    async def record_view(self, item_id: str, account: Account) -> None:
        await self._authorized_item(item_id, account)
        await self.repository.record_view(item_id, account.id)
