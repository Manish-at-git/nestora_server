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
        features = list((await self.session.scalars(statement)).all())
        features_by_id = {feature.id: feature for feature in features}
        children_by_parent: dict[str, list[Feature]] = {}
        root_features: list[Feature] = []

        for feature in features:
            if feature.parent_id and feature.parent_id in features_by_id:
                children_by_parent.setdefault(feature.parent_id, []).append(feature)
            else:
                root_features.append(feature)

        def sort_key(feature: Feature) -> tuple[int, str]:
            return (feature.order_index or 0, (feature.name or "").casefold())

        for children in children_by_parent.values():
            children.sort(key=sort_key)
        root_features.sort(key=sort_key)

        ordered_features: list[Feature] = []
        visited: set[str] = set()

        def append_branch(feature: Feature) -> None:
            if feature.id in visited:
                return
            visited.add(feature.id)
            ordered_features.append(feature)
            for child in children_by_parent.get(feature.id, []):
                append_branch(child)

        for feature in root_features:
            append_branch(feature)

        # Keep orphaned or cyclic records visible rather than dropping them.
        for feature in features:
            append_branch(feature)

        return ordered_features

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
