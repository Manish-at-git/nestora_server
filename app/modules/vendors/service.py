import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.vendors.messages import VendorMessage
from app.modules.vendors.models import Vendor
from app.modules.vendors.repository import VendorRepository
from app.modules.vendors.schemas import VendorRequest


class VendorService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = VendorRepository(session)

    async def list(self) -> list[Vendor]:
        return await self.repository.list()

    async def create(self, payload: VendorRequest) -> Vendor:
        if await self.repository.name_exists(payload.name):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, VendorMessage.NAME_EXISTS)
        vendor = Vendor(id=str(uuid.uuid4()), **payload.model_dump())
        self.repository.add(vendor)
        await self.repository.session.flush()
        await self.repository.session.refresh(vendor)
        return vendor

    async def update(self, vendor_id: str, payload: VendorRequest) -> Vendor:
        vendor = await self.repository.get(vendor_id)
        if vendor is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, VendorMessage.NOT_FOUND)
        if await self.repository.name_exists(payload.name, excluding_id=vendor_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, VendorMessage.NAME_EXISTS)
        for key, value in payload.model_dump().items():
            setattr(vendor, key, value)
        await self.repository.session.flush()
        return vendor

    async def delete(self, vendor_id: str) -> None:
        vendor = await self.repository.get(vendor_id)
        if vendor is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, VendorMessage.NOT_FOUND)
        vendor.is_deleted = True
