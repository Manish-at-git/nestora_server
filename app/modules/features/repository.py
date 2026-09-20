"""Database access for feature catalogue records."""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.iam.models import Feature


class FeatureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Feature]:
        statement: Select[tuple[Feature]] = (
            select(Feature)
            .options(joinedload(Feature.parent))
            .where(Feature.is_deleted.is_(False))
            .order_by(Feature.order_index, Feature.name)
        )
        return list((await self.session.scalars(statement)).all())

    async def get(self, feature_id: str) -> Feature | None:
        statement = (
            select(Feature)
            .options(joinedload(Feature.parent))
            .where(Feature.id == feature_id, Feature.is_deleted.is_(False))
        )
        return await self.session.scalar(statement)

    async def name_exists(self, name: str, excluding_id: str | None = None) -> bool:
        statement = select(Feature.id).where(
            func.lower(Feature.name) == name.lower(), Feature.is_deleted.is_(False)
        )
        if excluding_id:
            statement = statement.where(Feature.id != excluding_id)
        return await self.session.scalar(statement) is not None

    async def code_exists(self, code: str, excluding_id: str | None = None) -> bool:
        statement = select(Feature.id).where(
            func.lower(Feature.code) == code.lower(), Feature.is_deleted.is_(False)
        )
        if excluding_id:
            statement = statement.where(Feature.id != excluding_id)
        return await self.session.scalar(statement) is not None

    def add(self, feature: Feature) -> None:
        self.session.add(feature)

    async def soft_delete(self, feature: Feature) -> None:
        feature.is_deleted = True
        feature.is_active = False
        await self.session.flush()
