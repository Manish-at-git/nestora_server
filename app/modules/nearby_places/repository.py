"""Database access for Nearby Places."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.nearby_places.models import NearbyPlace


class NearbyPlaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, *, active_only: bool) -> list[NearbyPlace]:
        statement = select(NearbyPlace).order_by(NearbyPlace.created_at.desc())
        if active_only:
            statement = statement.where(NearbyPlace.is_active.is_(True))
        return list((await self.session.scalars(statement)).all())

    async def get(self, place_id: str) -> NearbyPlace | None:
        return await self.session.get(NearbyPlace, place_id)

    def add(self, place: NearbyPlace) -> None:
        self.session.add(place)

    async def delete(self, place: NearbyPlace) -> None:
        await self.session.delete(place)
