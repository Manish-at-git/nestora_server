"""API routes for Nearby Places."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import FeatureCode, RoleCode
from app.core.dependencies import get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.nearby_places.schemas import (
    NearbyPlaceCreate,
    NearbyPlaceMutationResponse,
    NearbyPlaceResponse,
    NearbyPlaceUpdate,
)
from app.modules.nearby_places.service import NearbyPlaceService

router = APIRouter(tags=[FeatureCode.NEARBY_PLACES.value])
admin_dependencies = [Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))]


@router.get("/nearby-places", response_model=ApiResponse[list[NearbyPlaceResponse]])
async def list_nearby_places(
    _: object = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return success_response(await NearbyPlaceService(session).list_active())


@router.get(
    "/admin/nearby-places",
    response_model=ApiResponse[list[NearbyPlaceResponse]],
    dependencies=admin_dependencies,
)
async def list_nearby_places_for_administration(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return success_response(await NearbyPlaceService(session).list_for_administration())


@router.post(
    "/admin/nearby-places",
    response_model=ApiResponse[NearbyPlaceResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=admin_dependencies,
)
async def create_nearby_place(
    payload: NearbyPlaceCreate,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        place = await NearbyPlaceService(session).create(payload)
    return success_response(place, "Nearby place created")


@router.put(
    "/admin/nearby-places/{place_id}",
    response_model=ApiResponse[NearbyPlaceResponse],
    dependencies=admin_dependencies,
)
async def update_nearby_place(
    place_id: str,
    payload: NearbyPlaceUpdate,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        place = await NearbyPlaceService(session).update(place_id, payload)
    return success_response(place, "Nearby place updated")


@router.delete(
    "/admin/nearby-places/{place_id}",
    response_model=ApiResponse[NearbyPlaceMutationResponse],
    dependencies=admin_dependencies,
)
async def delete_nearby_place(
    place_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await NearbyPlaceService(session).delete(place_id)
    return success_response(NearbyPlaceMutationResponse(message="Nearby place deleted"))
