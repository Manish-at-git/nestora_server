"""Pure subscription-trial lifecycle rules."""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class TrialInfo:
    subscription_status: str | None
    trial_days: int
    trial_days_left: int
    trial_display: str
    is_trial_expired: bool
    ends_on: date | None


@dataclass(frozen=True)
class SubscriptionExpiryInfo:
    """Derived access-period expiry based on the configured end date."""

    days_left: int | None
    display: str
    is_expired: bool


def calculate_effective_subscription_status(
    *, configured_status: str | None, subscription_end: date | None, today: date
) -> str:
    """Resolve the display status from the admin choice and the plan end date.

    ``Inactive`` is an explicit administrative choice. ``Expired`` is never
    persisted as a selectable value; it is derived when an otherwise active
    plan reaches its end date.
    """
    normalized_status = (configured_status or "Active").strip().casefold()
    if normalized_status in {"inactive", "cancelled", "canceled"}:
        return "Inactive"
    if subscription_end is not None and subscription_end <= today:
        return "Expired"
    return "Active"


def calculate_subscription_expiry(
    *, subscription_end: date | None, today: date
) -> SubscriptionExpiryInfo:
    """Describe the current plan period without using the renewal reminder date."""
    if subscription_end is None:
        return SubscriptionExpiryInfo(None, "No end date", False)
    days_left = max((subscription_end - today).days, 0)
    if days_left == 0:
        return SubscriptionExpiryInfo(0, "Expired", True)
    return SubscriptionExpiryInfo(days_left, f"{days_left} days left", False)


def calculate_trial_info(
    *,
    trial_days: int | None,
    subscription_status: str | None,
    subscription_start: date | None,
    subscription_end: date | None,
    today: date,
) -> TrialInfo:
    """Return derived trial state without mutating a persisted association."""
    days = max(int(trial_days or 0), 0)
    status = subscription_status or "Trial"
    if days == 0 or status != "Trial":
        return TrialInfo(status, days, 0, "No trial", False, subscription_end)

    ends_on = subscription_end or (
        subscription_start + timedelta(days=days) if subscription_start else None
    )
    if ends_on is None:
        return TrialInfo(status, days, days, f"{days}/{days} days", False, None)

    days_left = max((ends_on - today).days, 0)
    expired = days_left == 0
    return TrialInfo(
        "Expired" if expired else status,
        days,
        days_left,
        f"{days_left}/{days} days",
        expired,
        ends_on,
    )
