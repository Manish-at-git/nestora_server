"""Assessment-rate selection shared by resident-facing services."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AssessmentAmount:
    """The server-derived amount and the rule that produced it."""

    amount: Decimal
    rate_type: str


def resolve_assessment_amount(
    *,
    default_amount: Decimal | None,
    advanced_enabled: bool,
    owner_occupied_amount: Decimal | None,
    rented_amount: Decimal | None,
    is_rented: bool,
) -> AssessmentAmount:
    """Choose an occupancy-specific rate only when that configured rate exists."""
    fallback = Decimal(default_amount or 0)
    if advanced_enabled and is_rented and rented_amount is not None:
        return AssessmentAmount(Decimal(rented_amount), "Rented rate")
    if advanced_enabled and not is_rented and owner_occupied_amount is not None:
        return AssessmentAmount(Decimal(owner_occupied_amount), "Owner-occupied rate")
    return AssessmentAmount(fallback, "Standard rate")
