"""Fast unit checks for service-request input contracts and route coverage."""

import pytest
from pydantic import ValidationError

from app.modules.service_requests.constants import ServiceRequestStatus
from app.modules.service_requests.schemas import (
    ServiceRequestMessageRequest,
    ServiceRequestStatusRequest,
)


def test_legacy_status_aliases_normalize_to_canonical_values() -> None:
    assert ServiceRequestStatusRequest(status="Pending").status == ServiceRequestStatus.NEW
    assert ServiceRequestStatusRequest(status="Completed").status == ServiceRequestStatus.COMPLETE
    assert ServiceRequestStatusRequest(status="Cancelled").status == ServiceRequestStatus.CANCEL


def test_message_requires_text_or_attachment() -> None:
    with pytest.raises(ValidationError):
        ServiceRequestMessageRequest(message="  ", attachment_url="")


def test_all_legacy_service_request_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}
    expected = {
        ("POST", "/api/upload"),
        ("POST", "/api/service-requests"),
        ("GET", "/api/service-requests"),
        ("GET", "/api/service-requests/{request_id}"),
        ("PATCH", "/api/service-requests/{request_id}/status"),
        ("PATCH", "/api/service-requests/{request_id}/map"),
        ("POST", "/api/service-requests/{request_id}/messages"),
        ("GET", "/api/service-requests/{request_id}/messages"),
        ("GET", "/api/admin/associations/{association_id}/blocks"),
        ("GET", "/api/associations/{association_id}/blocks"),
        ("GET", "/api/admin/associations/{association_id}/all-units"),
        ("GET", "/api/admin/blocks/{block_id}/units"),
        ("GET", "/api/admin/units/{unit_id}/homeowners"),
        ("GET", "/api/notifications"),
        ("PATCH", "/api/notifications/{notification_id}/read"),
        ("POST", "/api/board-tasks"),
        ("GET", "/api/board-tasks"),
        ("GET", "/api/board-tasks/{task_id}"),
        ("DELETE", "/api/board-tasks/{task_id}"),
        ("GET", "/api/board-tasks/{task_id}/messages"),
        ("POST", "/api/board-tasks/{task_id}/messages"),
        ("PATCH", "/api/board-tasks/{task_id}/status"),
        ("GET", "/api/meetings"),
        ("POST", "/api/meetings"),
        ("DELETE", "/api/meetings/{meeting_id}"),
        ("POST", "/api/meetings/{meeting_id}/attendance"),
        ("PATCH", "/api/meetings/{meeting_id}/details"),
        ("PATCH", "/api/meetings/{meeting_id}/minutes"),
    }
    assert expected <= routes
