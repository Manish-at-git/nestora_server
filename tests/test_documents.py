"""Contract checks for association, resident, and unit document APIs."""

from datetime import date

from app.modules.documents.schemas import (
    DocumentRequest,
    DocumentUpdateRequest,
    UnitDocumentRequest,
    UnitDocumentUpdateRequest,
)


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
    assert "/api/board-visible-unit-documents" in paths
    assert "/api/admin/associations/{association_id}/all-units" in paths


def test_unit_document_request_defaults_to_private_board_visibility() -> None:
    payload = UnitDocumentRequest(name="Title deed", type="Property Document", file_url="https://example.test/deed.pdf")
    assert payload.is_visible_to_board is False


def test_unit_document_update_accepts_replacement_file_details() -> None:
    payload = UnitDocumentUpdateRequest(
        name="Rent Agreement",
        type="Rent Agreement",
        file_url="https://example.test/replacement.pdf",
        file_name="replacement.pdf",
        file_type="PDF",
        file_size_kb=128,
    )
    assert payload.file_name == "replacement.pdf"
