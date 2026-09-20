"""HTTP routes for service-request tickets and their supporting lookups."""

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.core.realtime import manager
from app.modules.notifications.service import publish_pending_notifications
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.service_requests.messages import ServiceRequestMessage
from app.modules.service_requests.schemas import (
    BlockResponse,
    ResidentResponse,
    ServiceRequestCreateRequest,
    ServiceRequestCreateResponse,
    ServiceRequestMappingRequest,
    ServiceRequestMessageCreateResponse,
    ServiceRequestMessageRequest,
    ServiceRequestMessageResponse,
    ServiceRequestMutationResponse,
    ServiceRequestResponse,
    ServiceRequestStatusRequest,
    UnitResponse,
)
from app.modules.service_requests.service import ServiceRequestService


router = APIRouter(prefix="/service-requests", tags=["Service Requests"])
lookup_router = APIRouter(tags=["Service Request Lookups"])


@router.get("", response_model=ApiResponse[list[ServiceRequestResponse]])
async def list_service_requests(
    association_id: str | None = None,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await ServiceRequestService(session).list(context.account, association_id)
    return success_response([ServiceRequestResponse(**row) for row in rows])


@router.post(
    "",
    response_model=ApiResponse[ServiceRequestCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_service_request(
    payload: ServiceRequestCreateRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        request_id = await ServiceRequestService(session).create(payload, context.account)
    await publish_pending_notifications(session)
    return success_response(
        ServiceRequestCreateResponse(id=request_id),
        ServiceRequestMessage.CREATED,
    )


@router.get("/{request_id}", response_model=ApiResponse[ServiceRequestResponse])
async def get_service_request(
    request_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    row = await ServiceRequestService(session).detail(request_id, context.account)
    return success_response(ServiceRequestResponse(**row))


@router.patch("/{request_id}/status", response_model=ApiResponse[ServiceRequestMutationResponse])
async def update_service_request_status(
    request_id: str,
    payload: ServiceRequestStatusRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await ServiceRequestService(session).update_status(
            request_id,
            payload.status,
            context.account,
        )
    await publish_pending_notifications(session)
    return success_response(ServiceRequestMutationResponse(), ServiceRequestMessage.UPDATED)


@router.patch("/{request_id}/map", response_model=ApiResponse[ServiceRequestMutationResponse])
async def map_service_request(
    request_id: str,
    payload: ServiceRequestMappingRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await ServiceRequestService(session).map(request_id, payload, context.account)
    await publish_pending_notifications(session)
    return success_response(ServiceRequestMutationResponse(), ServiceRequestMessage.MAPPED)


@router.delete("/{request_id}", response_model=ApiResponse[ServiceRequestMutationResponse])
async def delete_service_request(
    request_id: str,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await ServiceRequestService(session).delete(request_id, context.account)
    return success_response(ServiceRequestMutationResponse(), ServiceRequestMessage.DELETED)


@router.get(
    "/{request_id}/messages",
    response_model=ApiResponse[list[ServiceRequestMessageResponse]],
)
async def list_service_request_messages(
    request_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await ServiceRequestService(session).messages(request_id, context.account)
    return success_response([ServiceRequestMessageResponse(**row) for row in rows])


@router.post(
    "/{request_id}/messages",
    response_model=ApiResponse[ServiceRequestMessageCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def send_service_request_message(
    request_id: str,
    payload: ServiceRequestMessageRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        event = await ServiceRequestService(session).send_message(
            request_id,
            payload,
            context.account,
        )
    await manager.send_to_accounts(
        event.recipient_account_ids,
        {
            "type": "service_request.message",
            "request_id": event.request_id,
            "message": jsonable_encoder(event.message),
        },
    )
    await publish_pending_notifications(session)
    return success_response(
        ServiceRequestMessageCreateResponse(id=event.message["id"]),
        ServiceRequestMessage.MESSAGE_SENT,
    )


@lookup_router.get(
    "/associations/{association_id}/blocks",
    response_model=ApiResponse[list[BlockResponse]],
)
async def association_blocks(
    association_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await ServiceRequestService(session).blocks(association_id, context.account)
    return success_response([BlockResponse(**row) for row in rows])


@lookup_router.get(
    "/admin/associations/{association_id}/blocks",
    response_model=ApiResponse[list[BlockResponse]],
)
async def admin_association_blocks(
    association_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await ServiceRequestService(session).blocks(association_id, context.account)
    return success_response([BlockResponse(**row) for row in rows])


@lookup_router.get(
    "/admin/associations/{association_id}/all-units",
    response_model=ApiResponse[list[UnitResponse]],
)
async def association_units(
    association_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await ServiceRequestService(session).units(association_id, context.account)
    return success_response([UnitResponse(**row) for row in rows])


@lookup_router.get(
    "/admin/blocks/{block_id}/units",
    response_model=ApiResponse[list[UnitResponse]],
)
async def block_units(
    block_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await ServiceRequestService(session).block_units(block_id, context.account)
    return success_response([UnitResponse(**row) for row in rows])


@lookup_router.get(
    "/admin/units/{unit_id}/homeowners",
    response_model=ApiResponse[list[ResidentResponse]],
)
async def unit_residents(
    unit_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await ServiceRequestService(session).residents(unit_id, context.account)
    return success_response([ResidentResponse(**row) for row in rows])
