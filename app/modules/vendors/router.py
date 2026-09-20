from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.vendors.schemas import VendorMutationResponse, VendorRequest, VendorResponse
from app.modules.vendors.service import VendorService


router = APIRouter(
    prefix="/admin/vendors",
    tags=["Vendors"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)


@router.get("", response_model=ApiResponse[list[VendorResponse]])
async def list_vendors(session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response([VendorResponse.model_validate(v) for v in await VendorService(session).list()])


@router.post("", response_model=ApiResponse[VendorResponse], status_code=status.HTTP_201_CREATED)
async def create_vendor(
    payload: VendorRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        vendor = await VendorService(session).create(payload)
    return success_response(VendorResponse.model_validate(vendor), "Vendor created")


@router.put("/{vendor_id}", response_model=ApiResponse[VendorMutationResponse])
async def update_vendor(
    vendor_id: str,
    payload: VendorRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await VendorService(session).update(vendor_id, payload)
    return success_response(VendorMutationResponse(message="Vendor updated"))


@router.delete("/{vendor_id}", response_model=ApiResponse[VendorMutationResponse])
async def delete_vendor(
    vendor_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await VendorService(session).delete(vendor_id)
    return success_response(VendorMutationResponse(message="Vendor deleted"))
