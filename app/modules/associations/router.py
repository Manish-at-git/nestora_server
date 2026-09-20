"""Protected Association directory routes."""

from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.core.storage import StorageService
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.associations.schemas import (
    AssociationResponse,
    AssociationSettingsResponse,
    AssociationSettingsUpdateRequest,
    AssociationStats,
    AssociationSubscriptionRequest,
    MutationResponse,
    AssociationOnboardResponse,
)
from app.modules.associations.service import AssociationService


router = APIRouter(prefix="/admin/associations", tags=["Associations"])


@router.get(
    "/excel-template",
    dependencies=[
        Depends(
            require_role(
                RoleCode.SUPER_ADMIN,
                RoleCode.ADMIN,
                RoleCode.ACCOUNTANT,
                RoleCode.BOARD_MEMBER,
            )
        )
    ],
)
async def download_excel_template() -> StreamingResponse:
    """Return the onboarding workbook used by the association import flow."""
    from openpyxl import Workbook

    workbook = Workbook()
    sheets = {
        "Association Details": [
            "Association Name",
            "Association URL",
            "Address 1",
            "Address 2",
            "City",
            "State",
            "Pin Code",
            "Country",
        ],
        "Unit Details": ["Block Name", "Floor", "Unit Number"],
        "Homeowner Details": [
            "Block Name",
            "Unit Number",
            "First Name",
            "Last Name",
            "Email",
            "Phone Number",
            "Rented",
            "Tenant First Name",
            "Tenant Last Name",
            "Tenant Email Id",
            "Tenant Contact Number",
        ],
        "Board Members": [
            "Block Name",
            "Unit Number",
            "Role",
        ],
    }

    first_title, first_headers = next(iter(sheets.items()))
    first_sheet = workbook.active
    first_sheet.title = first_title
    first_sheet.append(first_headers)
    for title, headers in list(sheets.items())[1:]:
        worksheet = workbook.create_sheet(title)
        worksheet.append(headers)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=onboarding_template.xlsx"},
    )


@router.post(
    "/onboard/preview",
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def preview_onboarding_workbook(
    csv_file: UploadFile = File(...),
    _: object = Depends(require_csrf),
) -> dict:
    workbook_bytes = await csv_file.read()
    return success_response(
        AssociationService.workbook_metrics(workbook_bytes),
        "Onboarding workbook analyzed successfully",
    )


@router.post(
    "/onboard",
    response_model=ApiResponse[AssociationOnboardResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def onboard_association(
    entity_id: str = Form(...),
    plan_id: str | None = Form(None),
    contract_file: UploadFile | None = File(None),
    csv_file: UploadFile = File(...),
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    workbook_bytes = await csv_file.read()
    contract_url = None
    if contract_file and contract_file.filename:
        uploaded = await StorageService().upload(contract_file)
        contract_url = uploaded.get("url")
    async with UnitOfWork(session):
        result = await AssociationService(session).onboard(workbook_bytes, entity_id, plan_id, contract_url)
    return success_response(result, "Association onboarded successfully")


def serialize_association(association) -> AssociationResponse:
    return AssociationResponse(
        id=association.id,
        name=association.name,
        association_code=association.association_code,
        entity_id=association.entity_id,
        entity_name=association.entity.name if association.entity else None,
        address_line_1=association.address_line_1,
        address_line_2=association.address_line_2,
        city=association.city,
        state=association.state,
        pincode=association.pincode,
        country=association.country,
        url=association.url,
        association_url=association.url,
        contract_url=association.contract_url,
        current_plan_id=association.current_plan_id,
        plan_name=association.plan.name if association.plan else None,
        subscription_status=association.subscription_status,
        subscription_start=association.subscription_start,
        subscription_end=association.subscription_end,
        renewal_date=association.renewal_date,
        payment_status=association.payment_status,
        unit_count=getattr(association, "unit_count", 0),
        is_active=association.is_active,
        created_at=association.created_at,
        updated_at=association.updated_at,
        allowed_features=getattr(association, "allowed_features", []),
    )


@router.get(
    "",
    response_model=ApiResponse[list[AssociationResponse]],
    dependencies=[
        Depends(
            require_role(
                RoleCode.SUPER_ADMIN,
                RoleCode.ADMIN,
                RoleCode.ACCOUNTANT,
                RoleCode.BOARD_MEMBER,
            )
        )
    ],
)
async def list_associations(
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await AssociationService(session).list(context.account.id, context.account.role.code)
    return success_response([serialize_association(row) for row in rows])


@router.get(
    "/{association_id}/settings",
    response_model=ApiResponse[AssociationSettingsResponse],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def association_settings(
    association_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    settings = await AssociationService(session).settings(
        association_id,
        context.account.id,
        context.account.role.code,
    )
    return success_response(AssociationSettingsResponse(**settings))


@router.put(
    "/{association_id}/settings",
    response_model=ApiResponse[MutationResponse],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def update_association_settings(
    association_id: str,
    payload: AssociationSettingsUpdateRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await AssociationService(session).update_settings(
            association_id,
            payload,
            context.account.id,
            context.account.role.code,
        )
    return success_response(MutationResponse(), "Association settings updated")


@router.get(
    "/{association_id}/stats",
    response_model=ApiResponse[AssociationStats],
    dependencies=[
        Depends(
            require_role(
                RoleCode.SUPER_ADMIN,
                RoleCode.ADMIN,
                RoleCode.ACCOUNTANT,
                RoleCode.BOARD_MEMBER,
            )
        )
    ],
)
async def association_stats(association_id: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response(AssociationStats(**(await AssociationService(session).stats(association_id))))


@router.put(
    "/{association_id}/subscription",
    response_model=ApiResponse[MutationResponse],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)
async def update_association_subscription(
    association_id: str,
    payload: AssociationSubscriptionRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await AssociationService(session).update_subscription(association_id, payload)
    return success_response(MutationResponse())
