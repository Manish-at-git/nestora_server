"""Database access for Email Template Master."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.email_templates.models import EmailTemplate


class EmailTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[EmailTemplate]:
        statement = (
            select(EmailTemplate)
            .where(EmailTemplate.is_deleted.is_(False))
            .order_by(EmailTemplate.created_at.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def get(self, template_id: str) -> EmailTemplate | None:
        statement = select(EmailTemplate).where(
            EmailTemplate.id == template_id,
            EmailTemplate.is_deleted.is_(False),
        )
        return await self.session.scalar(statement)

    async def get_active_by_event_type(self, event_type: str) -> EmailTemplate | None:
        statement = select(EmailTemplate).where(
            func.lower(EmailTemplate.event_type) == event_type.lower(),
            EmailTemplate.is_active.is_(True),
            EmailTemplate.is_deleted.is_(False),
        )
        return await self.session.scalar(statement)

    async def event_type_exists(
        self,
        event_type: str,
        excluding_id: str | None = None,
    ) -> bool:
        statement = select(EmailTemplate.id).where(
            func.lower(EmailTemplate.event_type) == event_type.lower(),
            EmailTemplate.is_deleted.is_(False),
        )
        if excluding_id is not None:
            statement = statement.where(EmailTemplate.id != excluding_id)
        return await self.session.scalar(statement) is not None

    def add(self, template: EmailTemplate) -> None:
        self.session.add(template)

    async def delete(self, template: EmailTemplate) -> None:
        template.is_deleted = True
        template.is_active = False
        await self.session.flush()
