"""Protected Super Admin routes for Email Template Master."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import FeatureCode, RoleCode
from app.core.dependencies import require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.email_templates.schemas import (
    EmailTemplateMutationResponse,
    EmailTemplateRequest,
    EmailTemplateResponse,
    EmailTemplateTestRequest,
    EmailTemplateTestResponse,
)
from app.modules.email_templates.service import EmailTemplateService


router = APIRouter(
    prefix="/admin/email-templates",
    tags=[FeatureCode.EMAIL_TEMPLATES.value],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)


@router.get("", response_model=ApiResponse[list[EmailTemplateResponse]])
async def list_email_templates(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    templates = await EmailTemplateService(session).list()
    return success_response(
        [EmailTemplateResponse.model_validate(template) for template in templates]
    )


@router.post(
    "",
    response_model=ApiResponse[EmailTemplateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_email_template(
    payload: EmailTemplateRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        template = await EmailTemplateService(session).create(payload)
    return success_response(EmailTemplateResponse.model_validate(template))


@router.put(
    "/{template_id}",
    response_model=ApiResponse[EmailTemplateMutationResponse],
)
async def update_email_template(
    template_id: str,
    payload: EmailTemplateRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await EmailTemplateService(session).update(template_id, payload)
    return success_response(EmailTemplateMutationResponse())


@router.delete(
    "/{template_id}",
    response_model=ApiResponse[EmailTemplateMutationResponse],
)
async def delete_email_template(
    template_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await EmailTemplateService(session).delete(template_id)
    return success_response(EmailTemplateMutationResponse())


@router.post(
    "/{template_id}/test",
    response_model=ApiResponse[EmailTemplateTestResponse],
)
async def send_test_email(
    template_id: str,
    payload: EmailTemplateTestRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    result = await EmailTemplateService(session).send_test(template_id, payload)
    return success_response(result, "Test email sent")
