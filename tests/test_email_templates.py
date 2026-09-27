"""Unit and route-contract checks for Email Template Master."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.email_templates.messages import EmailTemplateMessage
from app.modules.email_templates.schemas import EmailTemplateRequest
from app.modules.email_templates.service import EmailTemplateService


def test_email_template_request_normalizes_required_fields() -> None:
    payload = EmailTemplateRequest(
        name="  Community Announcement  ",
        event_type="  Announcement Created  ",
        subject="  New announcement  ",
        body="  <p>Hello</p>  ",
    )

    assert payload.name == "Community Announcement"
    assert payload.event_type == "announcement_created"
    assert payload.subject == "New announcement"
    assert payload.body == "<p>Hello</p>"


@pytest.mark.parametrize("field_name", ["name", "subject", "body"])
def test_email_template_request_rejects_blank_required_text(field_name: str) -> None:
    values = {
        "name": "Template",
        "event_type": "custom_event",
        "subject": "Subject",
        "body": "Body",
    }
    values[field_name] = "   "

    with pytest.raises(ValidationError, match="This field is required"):
        EmailTemplateRequest(**values)


def test_email_template_request_rejects_invalid_event_type() -> None:
    with pytest.raises(ValidationError, match="Event type must start with a letter"):
        EmailTemplateRequest(
            name="Template",
            event_type="123 invalid-event",
            subject="Subject",
            body="Body",
        )


@pytest.mark.asyncio
async def test_create_rejects_duplicate_event_type() -> None:
    service = EmailTemplateService(AsyncMock())
    service.repository.event_type_exists = AsyncMock(return_value=True)

    with pytest.raises(HTTPException) as error:
        await service.create(
            EmailTemplateRequest(
                name="Template",
                event_type="announcement_created",
                subject="Subject",
                body="Body",
            )
        )

    assert error.value.status_code == 400
    assert error.value.detail == EmailTemplateMessage.EVENT_TYPE_EXISTS


@pytest.mark.asyncio
async def test_delete_uses_soft_delete_repository_method() -> None:
    service = EmailTemplateService(AsyncMock())
    template = SimpleNamespace(id="template-1")
    service.repository.get = AsyncMock(return_value=template)
    service.repository.delete = AsyncMock()

    await service.delete(template.id)

    service.repository.delete.assert_awaited_once_with(template)


def test_render_preserves_unknown_variables() -> None:
    rendered = EmailTemplateService.render(
        "Hello {homeowner_name}, {unknown_value}",
        {"homeowner_name": "Sarah"},
    )

    assert rendered == "Hello Sarah, {unknown_value}"


def test_email_template_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
    }

    assert {
        ("GET", "/api/admin/email-templates"),
        ("POST", "/api/admin/email-templates"),
        ("PUT", "/api/admin/email-templates/{template_id}"),
        ("DELETE", "/api/admin/email-templates/{template_id}"),
        ("POST", "/api/admin/email-templates/{template_id}/test"),
    } <= routes
