"""Contract checks for marketplace listing and chat APIs."""

from decimal import Decimal

from app.modules.marketplace.schemas import MarketplaceItemRequest, MarketplaceReportRequest


def test_marketplace_item_request_accepts_listing_fields() -> None:
    payload = MarketplaceItemRequest(title="Desk", category_id="category-1", price=Decimal("1250"))
    assert payload.price == Decimal("1250")
    assert payload.listing_type == "Sell"


def test_marketplace_report_requires_a_reason() -> None:
    payload = MarketplaceReportRequest(reason="Misleading listing")
    assert payload.reason.startswith("Misleading")


def test_marketplace_routes_are_registered(monkeypatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/marketplace/categories" in paths
    assert "/api/marketplace/items" in paths
    assert "/api/marketplace/chat/{item_id}" in paths
