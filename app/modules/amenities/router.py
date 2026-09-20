"""HTTP routes for amenity management and reservations."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.amenities.messages import AmenityMessage
from app.modules.amenities.schemas import (
    AmenityBookingCreateResponse,
    AmenityBookingListResponse,
    AmenityBookingRequest,
    AmenityBookingResponse,
    AmenityCreateRequest,
    AmenityCreateResponse,
    AmenityListResponse,
    AmenityMutationResponse,
    AmenityResponse,
    AmenitySlotResponse,
    AmenityStatusRequest,
)
from app.modules.amenities.service import AmenityService


router = APIRouter(tags=["Amenities"])


@router.get("/admin/associations/{association_id}/amenities", response_model=AmenityListResponse)
async def list_admin_amenities(
    association_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await AmenityService(session).list_admin(association_id, context.account)
    return success_response([AmenityResponse(**row) for row in rows])


@router.post(
    "/admin/associations/{association_id}/amenities",
    response_model=ApiResponse[AmenityCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_amenity(
    association_id: str,
    payload: AmenityCreateRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        amenity_id = await AmenityService(session).create(association_id, payload, context.account)
    return success_response(AmenityCreateResponse(id=amenity_id), AmenityMessage.CREATED)


@router.put(
    "/admin/associations/{association_id}/amenities/{amenity_id}",
    response_model=ApiResponse[AmenityMutationResponse],
)
async def update_amenity_status(
    association_id: str,
    amenity_id: str,
    payload: AmenityStatusRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await AmenityService(session).update_status(association_id, amenity_id, payload, context.account)
    return success_response(AmenityMutationResponse(), AmenityMessage.STATUS_UPDATED)


@router.delete(
    "/admin/associations/{association_id}/amenities/{amenity_id}",
    response_model=ApiResponse[AmenityMutationResponse],
)
async def delete_amenity(
    association_id: str,
    amenity_id: str,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await AmenityService(session).delete(association_id, amenity_id, context.account)
    return success_response(AmenityMutationResponse(), AmenityMessage.DELETED)


@router.get("/admin/associations/{association_id}/amenity-bookings", response_model=AmenityBookingListResponse)
async def list_association_bookings(
    association_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await AmenityService(session).association_bookings(association_id, context.account)
    return success_response([AmenityBookingResponse(**row) for row in rows])


@router.get("/associations/{association_id}/amenities", response_model=AmenityListResponse)
async def list_active_amenities(
    association_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await AmenityService(session).list_active(association_id, context.account)
    return success_response([AmenityResponse(**row) for row in rows])


@router.get("/amenities/{amenity_id}/bookings", response_model=ApiResponse[list[AmenitySlotResponse]])
async def list_amenity_month_bookings(
    amenity_id: str,
    month: str | None = None,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await AmenityService(session).month_slots(amenity_id, month or "", context.account)
    return success_response([AmenitySlotResponse(**row) for row in rows])


@router.get("/amenities/my-bookings", response_model=AmenityBookingListResponse)
async def list_my_bookings(
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await AmenityService(session).my_bookings(context.account)
    return success_response([AmenityBookingResponse(**row) for row in rows])


@router.post(
    "/amenities/{amenity_id}/book",
    response_model=ApiResponse[AmenityBookingCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def book_amenity(
    amenity_id: str,
    payload: AmenityBookingRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        booking_id = await AmenityService(session).book(amenity_id, payload, context.account)
    return success_response(AmenityBookingCreateResponse(booking_id=booking_id), AmenityMessage.BOOKED)
