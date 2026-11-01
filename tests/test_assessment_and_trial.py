from datetime import date
from decimal import Decimal

import pytest

from app.modules.associations.assessment import resolve_assessment_amount
from app.modules.subscriptions.trial import (
    calculate_effective_subscription_status,
    calculate_subscription_expiry,
    calculate_trial_info,
)


@pytest.mark.parametrize(
    ("advanced_enabled", "is_rented", "owner_rate", "rented_rate", "expected_amount", "expected_type"),
    [
        (False, False, Decimal("1200"), Decimal("1500"), Decimal("1000"), "Standard rate"),
        (True, False, Decimal("1200"), Decimal("1500"), Decimal("1200"), "Owner-occupied rate"),
        (True, True, Decimal("1200"), Decimal("1500"), Decimal("1500"), "Rented rate"),
        (True, True, Decimal("1200"), None, Decimal("1000"), "Standard rate"),
    ],
)
def test_assessment_amount_uses_configured_occupancy_rate(
    advanced_enabled: bool,
    is_rented: bool,
    owner_rate: Decimal | None,
    rented_rate: Decimal | None,
    expected_amount: Decimal,
    expected_type: str,
) -> None:
    result = resolve_assessment_amount(
        default_amount=Decimal("1000"),
        advanced_enabled=advanced_enabled,
        owner_occupied_amount=owner_rate,
        rented_amount=rented_rate,
        is_rented=is_rented,
    )

    assert result.amount == expected_amount
    assert result.rate_type == expected_type


def test_trial_expires_on_its_configured_end_date() -> None:
    result = calculate_trial_info(
        trial_days=14,
        subscription_status="Trial",
        subscription_start=date(2026, 10, 18),
        subscription_end=date(2026, 11, 1),
        today=date(2026, 11, 1),
    )

    assert result.is_trial_expired is True
    assert result.subscription_status == "Expired"
    assert result.trial_days_left == 0


def test_active_subscription_is_not_treated_as_an_expired_trial() -> None:
    result = calculate_trial_info(
        trial_days=14,
        subscription_status="Active",
        subscription_start=date(2026, 10, 1),
        subscription_end=date(2026, 10, 15),
        today=date(2026, 11, 1),
    )

    assert result.is_trial_expired is False
    assert result.subscription_status == "Active"


def test_subscription_expiry_uses_end_date_not_renewal_date() -> None:
    result = calculate_subscription_expiry(
        subscription_end=date(2026, 11, 26),
        today=date(2026, 11, 1),
    )

    assert result.days_left == 25
    assert result.display == "25 days left"
    assert result.is_expired is False


def test_effective_subscription_status_prioritizes_inactive_then_end_date() -> None:
    assert calculate_effective_subscription_status(
        configured_status="Inactive", subscription_end=date(2026, 12, 1), today=date(2026, 11, 1)
    ) == "Inactive"
    assert calculate_effective_subscription_status(
        configured_status="Active", subscription_end=date(2026, 10, 31), today=date(2026, 11, 1)
    ) == "Expired"
    assert calculate_effective_subscription_status(
        configured_status="Active", subscription_end=date(2026, 12, 1), today=date(2026, 11, 1)
    ) == "Active"
