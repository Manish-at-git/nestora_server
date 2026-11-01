import pytest
from pydantic import ValidationError

from app.modules.subscriptions.schemas import SubscriptionPlanRequest


@pytest.mark.parametrize(
    ("country", "expected"),
    [
        ("IN", "IN"),
        ("india", "IN"),
        ("USA", "US"),
        ("United Kingdom", "GB"),
    ],
)
def test_subscription_plan_normalizes_supported_country_values(
    country: str, expected: str
) -> None:
    plan = SubscriptionPlanRequest(name="Starter", country=country)
    assert plan.country == expected


def test_subscription_plan_rejects_unknown_country() -> None:
    with pytest.raises(ValidationError, match="supported country"):
        SubscriptionPlanRequest(name="Starter", country="Unknown")
