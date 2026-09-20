"""Contract checks for association, resident, and unit document APIs."""

from datetime import date

from app.modules.documents.schemas import DocumentRequest, DocumentUpdateRequest


def test_document_request_accepts_legacy_fields() -> None:
    payload = DocumentRequest(
        association_id="association-1",
        title="House Rules",
        issue_date=date(2026, 1, 1),
        visibility="Residents",
    )
    assert payload.issue_date == date(2026, 1, 1)
    assert payload.visibility == "Residents"


def test_document_update_does_not_require_association_id() -> None:
    payload = DocumentUpdateRequest(title="Updated Rules")
    assert payload.title == "Updated Rules"


def test_document_routes_are_registered(monkeypatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/admin/documents" in paths
    assert "/api/unit-documents/{document_id}" in paths
    assert "/api/admin/associations/{association_id}/all-units" in paths
