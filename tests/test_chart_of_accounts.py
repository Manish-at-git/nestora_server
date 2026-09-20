"""Contract checks for the separate Chart of Accounts API."""

from app.modules.chart_of_accounts.schemas import ChartOfAccountRequest


def test_chart_of_account_request_requires_code_and_name() -> None:
    payload = ChartOfAccountRequest(gl_code="1000", gl_name="Cash")
    assert payload.gl_code == "1000"


def test_chart_of_accounts_routes_are_registered(monkeypatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/admin/global-coa" in paths
    assert "/api/accountant/association-coa" in paths
    assert "/api/accountant/association-coa/{account_id}" in paths
