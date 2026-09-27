"""Business rules for the global Nearby Places catalogue."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.nearby_places.messages import NearbyPlaceMessage
from app.modules.nearby_places.models import NearbyPlace
from app.modules.nearby_places.repository import NearbyPlaceRepository
from app.modules.nearby_places.schemas import NearbyPlaceCreate, NearbyPlaceUpdate


class NearbyPlaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = NearbyPlaceRepository(session)

    async def list_active(self) -> list[NearbyPlace]:
        return await self.repository.list(active_only=True)

    async def list_for_administration(self) -> list[NearbyPlace]:
        return await self.repository.list(active_only=False)

    async def create(self, payload: NearbyPlaceCreate) -> NearbyPlace:
        place = NearbyPlace(id=str(uuid.uuid4()), **payload.model_dump())
        self.repository.add(place)
        await self.repository.session.flush()
        await self.repository.session.refresh(place)
        return place

    async def update(self, place_id: str, payload: NearbyPlaceUpdate) -> NearbyPlace:
        place = await self._get_or_404(place_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(place, field, value)
        await self.repository.session.flush()
        await self.repository.session.refresh(place)
        return place

    async def delete(self, place_id: str) -> None:
        place = await self._get_or_404(place_id)
        await self.repository.delete(place)
        await self.repository.session.flush()

    async def _get_or_404(self, place_id: str) -> NearbyPlace:
        place = await self.repository.get(place_id)
        if place is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NearbyPlaceMessage.NOT_FOUND)
        return place
