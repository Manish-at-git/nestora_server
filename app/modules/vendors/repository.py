from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.vendors.models import Vendor


class VendorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Vendor]:
        result = await self.session.scalars(
            select(Vendor).where(Vendor.is_deleted.is_(False)).order_by(Vendor.created_at.desc())
        )
        return list(result.all())

    async def get(self, vendor_id: str) -> Vendor | None:
        return await self.session.scalar(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.is_deleted.is_(False))
        )

    async def name_exists(self, name: str, excluding_id: str | None = None) -> bool:
        statement = select(Vendor.id).where(
            func.lower(Vendor.name) == name.strip().lower(), Vendor.is_deleted.is_(False)
        )
        if excluding_id:
            statement = statement.where(Vendor.id != excluding_id)
        return await self.session.scalar(statement) is not None

    def add(self, vendor: Vendor) -> None:
        self.session.add(vendor)
