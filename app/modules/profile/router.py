"""Cookie-authenticated profile routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_db_session, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.db.unit_of_work import UnitOfWork
from app.modules.profile.repository import ProfileRepository
from app.modules.profile.schemas import (
    EducationRequest, ExperienceRequest, FamilyMemberRequest, PetRequest, ProfileData,
    ProfileMutationResponse, ProfileUpdateRequest, VehicleRequest,
)
from app.modules.profile.service import ProfileService

router = APIRouter(prefix="/profile", tags=["Profile"])


def get_service(session: AsyncSession = Depends(get_db_session)) -> ProfileService:
    return ProfileService(ProfileRepository(session))


@router.get("/data", response_model=ApiResponse[ProfileData])
async def profile_data(context: AuthContext = Depends(get_auth_context), service: ProfileService = Depends(get_service)) -> dict:
    return success_response(await service.data(context.account))


@router.put("/user-details", response_model=ApiResponse[ProfileMutationResponse])
async def update_user_details(payload: ProfileUpdateRequest, _: AuthContext = Depends(require_csrf), context: AuthContext = Depends(get_auth_context), service: ProfileService = Depends(get_service)) -> dict:
    async with UnitOfWork(service.repository.session):
        await service.update_details(context.account, payload)
    return success_response(ProfileMutationResponse(), "Profile details updated successfully")


@router.post("/family-members", response_model=ApiResponse[ProfileMutationResponse], status_code=status.HTTP_201_CREATED)
async def add_family_member(payload: FamilyMemberRequest, _: AuthContext = Depends(require_csrf), context: AuthContext = Depends(get_auth_context), service: ProfileService = Depends(get_service)) -> dict:
    async with UnitOfWork(service.repository.session):
        record_id = await service.family_member(context.account, payload)
    return success_response(ProfileMutationResponse(id=record_id), "Family member added successfully")


def _member_routes(path: str, table: str, schema, label: str):
    async def create(payload, _: AuthContext = Depends(require_csrf), context: AuthContext = Depends(get_auth_context), service: ProfileService = Depends(get_service)):
        async with UnitOfWork(service.repository.session):
            record_id = await service.member_record(table, context.account, payload)
        return success_response(ProfileMutationResponse(id=record_id), f"{label} added successfully")
    create.__annotations__["payload"] = schema
    router.add_api_route(path, create, methods=["POST"], response_model=ApiResponse[ProfileMutationResponse], status_code=status.HTTP_201_CREATED)

    async def update(record_id: str, payload, _: AuthContext = Depends(require_csrf), context: AuthContext = Depends(get_auth_context), service: ProfileService = Depends(get_service)):
        async with UnitOfWork(service.repository.session):
            await service.member_record(table, context.account, payload, record_id)
        return success_response(ProfileMutationResponse(id=record_id), f"{label} updated successfully")
    update.__annotations__["payload"] = schema
    router.add_api_route(f"{path}/{{record_id}}", update, methods=["PUT"], response_model=ApiResponse[ProfileMutationResponse])

    async def delete(record_id: str, _: AuthContext = Depends(require_csrf), context: AuthContext = Depends(get_auth_context), service: ProfileService = Depends(get_service)):
        async with UnitOfWork(service.repository.session):
            await service.delete_member_record(table, context.account, record_id)
        return success_response(ProfileMutationResponse(), f"{label} deleted successfully")
    router.add_api_route(f"{path}/{{record_id}}", delete, methods=["DELETE"], response_model=ApiResponse[ProfileMutationResponse])


def _employee_routes(path: str, table: str, schema, label: str):
    async def create(payload, _: AuthContext = Depends(require_csrf), context: AuthContext = Depends(get_auth_context), service: ProfileService = Depends(get_service)):
        async with UnitOfWork(service.repository.session):
            record_id = await service.employee_record(table, context.account, payload)
        return success_response(ProfileMutationResponse(id=record_id), f"{label} added successfully")
    create.__annotations__["payload"] = schema
    router.add_api_route(path, create, methods=["POST"], response_model=ApiResponse[ProfileMutationResponse], status_code=status.HTTP_201_CREATED)

    async def update(record_id: str, payload, _: AuthContext = Depends(require_csrf), context: AuthContext = Depends(get_auth_context), service: ProfileService = Depends(get_service)):
        async with UnitOfWork(service.repository.session):
            await service.employee_record(table, context.account, payload, record_id)
        return success_response(ProfileMutationResponse(id=record_id), f"{label} updated successfully")
    update.__annotations__["payload"] = schema
    router.add_api_route(f"{path}/{{record_id}}", update, methods=["PUT"], response_model=ApiResponse[ProfileMutationResponse])

    async def delete(record_id: str, _: AuthContext = Depends(require_csrf), context: AuthContext = Depends(get_auth_context), service: ProfileService = Depends(get_service)):
        async with UnitOfWork(service.repository.session):
            await service.delete_employee_record(table, context.account, record_id)
        return success_response(ProfileMutationResponse(), f"{label} deleted successfully")
    router.add_api_route(f"{path}/{{record_id}}", delete, methods=["DELETE"], response_model=ApiResponse[ProfileMutationResponse])


_member_routes("/vehicles", "vehicles", VehicleRequest, "Vehicle")
_member_routes("/pets", "pets", PetRequest, "Pet")
_employee_routes("/education", "employee_education", EducationRequest, "Education")
_employee_routes("/experience", "employee_experience", ExperienceRequest, "Experience")
