"""Business rules for Email Template Master."""

import re
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailService
from app.modules.email_templates.constants import DEFAULT_SAMPLE_CONTEXT
from app.modules.email_templates.messages import EmailTemplateMessage
from app.modules.email_templates.models import EmailTemplate
from app.modules.email_templates.repository import EmailTemplateRepository
from app.modules.email_templates.schemas import (
    EmailTemplateRequest,
    EmailTemplateTestRequest,
    EmailTemplateTestResponse,
)


PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z][a-zA-Z0-9_]*)\}")


class EmailTemplateService:
    def __init__(
        self,
        session: AsyncSession,
        email_service: EmailService | None = None,
    ) -> None:
        self.repository = EmailTemplateRepository(session)
        self.email_service = email_service or EmailService()

    async def list(self) -> list[EmailTemplate]:
        return await self.repository.list()

    async def get_active_by_event_type(self, event_type: str) -> EmailTemplate | None:
        return await self.repository.get_active_by_event_type(event_type)

    async def render_active(
        self, event_type: str, context: dict[str, Any]
    ) -> tuple[str, str] | None:
        template = await self.get_active_by_event_type(event_type)
        if template is None:
            return None
        return self.render(template.subject, context), self.render(template.body, context)

    async def create(self, payload: EmailTemplateRequest) -> EmailTemplate:
        await self._ensure_unique_event_type(payload.event_type)
        template = EmailTemplate(
            id=str(uuid.uuid4()),
            name=payload.name,
            event_type=payload.event_type,
            subject=payload.subject,
            body=payload.body,
            is_active=payload.is_active,
        )
        self.repository.add(template)
        await self.repository.session.flush()
        await self.repository.session.refresh(template)
        return template

    async def update(
        self,
        template_id: str,
        payload: EmailTemplateRequest,
    ) -> EmailTemplate:
        template = await self._get_or_404(template_id)
        await self._ensure_unique_event_type(payload.event_type, excluding_id=template_id)
        template.name = payload.name
        template.event_type = payload.event_type
        template.subject = payload.subject
        template.body = payload.body
        template.is_active = payload.is_active
        await self.repository.session.flush()
        return template

    async def delete(self, template_id: str) -> None:
        template = await self._get_or_404(template_id)
        await self.repository.delete(template)

    async def send_test(
        self,
        template_id: str,
        payload: EmailTemplateTestRequest,
    ) -> EmailTemplateTestResponse:
        template = await self._get_or_404(template_id)
        context = {**DEFAULT_SAMPLE_CONTEXT, **(payload.sample_context or {})}
        subject = self.render(template.subject, context)
        body = self.render(template.body, context)
        result = await self.email_service.send_email(
            to_email=str(payload.test_email),
            subject=subject,
            html_content=body,
        )
        if not result.get("ok"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=EmailTemplateMessage.TEST_SEND_FAILED,
            )
        return EmailTemplateTestResponse(
            provider=str(result.get("provider")) if result.get("provider") else None
        )

    @staticmethod
    def render(content: str, context: dict[str, Any]) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            value = context.get(key)
            return str(value) if value is not None else match.group(0)

        return PLACEHOLDER_PATTERN.sub(replace, content)

    async def _get_or_404(self, template_id: str) -> EmailTemplate:
        template = await self.repository.get(template_id)
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=EmailTemplateMessage.NOT_FOUND,
            )
        return template

    async def _ensure_unique_event_type(
        self,
        event_type: str,
        excluding_id: str | None = None,
    ) -> None:
        if await self.repository.event_type_exists(event_type, excluding_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=EmailTemplateMessage.EVENT_TYPE_EXISTS,
            )
