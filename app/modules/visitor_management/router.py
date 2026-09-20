"""Visitor, gate, pass, and delivery APIs."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.visitor_management.schemas import (
    CheckInRequest,
    DeliveryRequest,
    MutationResponse,
    PreApprovedVisitorRequest,
    VisitorRequest,
)
from app.modules.visitor_management.service import VisitorManagementService


router = APIRouter(tags=["Visitor Management"])
VIEW_DEP = Depends(require_role(*tuple(RoleCode)))
SECURITY_DEP = Depends(require_role(RoleCode.SECURITY, RoleCode.ADMIN, RoleCode.SUPER_ADMIN))


@router.get("/security/visitors/search", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def search_visitor(mobile: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    row = await VisitorManagementService(session).repository.find_visitor(mobile)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Visitor not found")
    return success_response(row)


@router.get("/security/residents/search", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def search_residents(q: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response({"residents": await VisitorManagementService(session).repository.resident_search(q)})


@router.post("/security/visitor/request", response_model=ApiResponse[MutationResponse], status_code=status.HTTP_201_CREATED)
async def request_visitor(payload: VisitorRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        visit_id = await VisitorManagementService(session).create_request(payload, context.account)
    return success_response(MutationResponse(id=visit_id, message="Request sent to resident"))


@router.get("/security/visitor/status/{visit_id}", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def visitor_status(visit_id: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    row = await VisitorManagementService(session).repository.get_visit(visit_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Visit not found")
    return success_response(row)


@router.get("/resident/visitor/pending", response_model=ApiResponse[dict], dependencies=[VIEW_DEP])
async def pending_requests(context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    service = VisitorManagementService(session)
    unit_id = await service.resident_unit(context.account)
    return success_response({"requests": await service.repository.pending_visits(unit_id)})


@router.post("/resident/visitor/{visit_id}/approve", response_model=ApiResponse[MutationResponse])
async def approve_visitor(visit_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        pass_code = await VisitorManagementService(session).approve(visit_id, context.account, True)
    return success_response(MutationResponse(pass_code=pass_code))


@router.post("/resident/visitor/{visit_id}/reject", response_model=ApiResponse[MutationResponse])
async def reject_visitor(visit_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await VisitorManagementService(session).approve(visit_id, context.account, False)
    return success_response(MutationResponse())


@router.post("/resident/preapproved-visitors", response_model=ApiResponse[MutationResponse], status_code=status.HTTP_201_CREATED)
async def create_preapproved(payload: PreApprovedVisitorRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        pass_id, pass_code, otp = await VisitorManagementService(session).create_preapproved(payload, context.account)
    return success_response(MutationResponse(id=pass_id, pass_code=pass_code, otp=otp))


@router.get("/resident/preapproved-visitors", response_model=ApiResponse[dict], dependencies=[VIEW_DEP])
async def resident_preapproved(context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    service = VisitorManagementService(session)
    unit_id = await service.resident_unit(context.account)
    return success_response({"visitors": await service.repository.resident_preapproved(unit_id)})


@router.get("/public/visitor-passes/{pass_code}", response_model=ApiResponse[dict])
async def public_pass(pass_code: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    row = await VisitorManagementService(session).repository.get_pass(pass_code=pass_code)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Visitor pass not found")
    return success_response(row)


@router.delete("/resident/preapproved-visitors/{pass_id}", response_model=ApiResponse[MutationResponse])
async def cancel_preapproved(pass_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        service = VisitorManagementService(session)
        unit_id = await service.resident_unit(context.account)
        if not await service.repository.cancel_pass(pass_id, unit_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Visitor pass not found")
    return success_response(MutationResponse())


@router.get("/security/preapproved-visitors/today", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def today_preapproved(session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response({"visitors": await VisitorManagementService(session).repository.passes(today=True)})


@router.get("/security/preapproved-visitors/search", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def search_preapproved(q: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response({"visitors": await VisitorManagementService(session).repository.passes(search=q)})


@router.post("/security/preapproved-visitors/{pass_id}/check-in", response_model=ApiResponse[MutationResponse])
async def check_in(pass_id: str, payload: CheckInRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        log_id = await VisitorManagementService(session).check_in(pass_id, payload.model_dump(), context.account)
    return success_response(MutationResponse(log_id=log_id))


@router.post("/security/preapproved-visitors/{pass_id}/check-out", response_model=ApiResponse[MutationResponse])
async def check_out(pass_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        log_id = await VisitorManagementService(session).check_out(pass_id, context.account)
    return success_response(MutationResponse(log_id=log_id))


@router.post("/security/visitors/log/{log_id}/check-out", response_model=ApiResponse[MutationResponse])
async def check_out_log(log_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await VisitorManagementService(session).check_out_log(log_id, context.account)
    return success_response(MutationResponse(log_id=log_id))


@router.get("/security/visitors/checkin-list", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def checkin_list(session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response({"visitors": await VisitorManagementService(session).repository.visitor_queue()})


@router.get("/security/visitors/checkout-list", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def checkout_list(session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response({"visitors": await VisitorManagementService(session).repository.visitor_queue(24)})


@router.get("/security/visitors/history", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def visitor_history(session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response({"visitors": await VisitorManagementService(session).repository.history()})


@router.post("/security/deliveries", response_model=ApiResponse[MutationResponse], status_code=status.HTTP_201_CREATED)
async def create_delivery(payload: DeliveryRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        delivery_id = await VisitorManagementService(session).create_delivery(payload, context.account)
    return success_response(MutationResponse(id=delivery_id))


@router.get("/security/deliveries/active", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def active_deliveries(session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response({"deliveries": await VisitorManagementService(session).repository.deliveries(active=True)})


@router.post("/security/deliveries/{delivery_id}/complete", response_model=ApiResponse[MutationResponse])
async def complete_delivery(delivery_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await VisitorManagementService(session).complete_delivery(delivery_id, context.account)
    return success_response(MutationResponse(id=delivery_id))


@router.get("/security/deliveries/history", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def delivery_history(session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response({"deliveries": await VisitorManagementService(session).repository.deliveries()})


@router.get("/resident/deliveries", response_model=ApiResponse[dict], dependencies=[VIEW_DEP])
async def resident_deliveries(context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    service = VisitorManagementService(session)
    return success_response({"deliveries": await service.repository.deliveries(await service.resident_unit(context.account))})


@router.get("/security/vehicles", response_model=ApiResponse[dict], dependencies=[SECURITY_DEP])
async def vehicles(session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response({"vehicles": await VisitorManagementService(session).repository.vehicles()})
