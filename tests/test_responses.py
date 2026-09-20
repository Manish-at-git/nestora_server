"""Small unit tests for the shared response utility; database tests come after an isolated test DB is configured."""

from app.core.responses import success_response


def test_success_response_has_the_fixed_shape() -> None:
    """Every successful endpoint should return the same four outer response fields."""
    response = success_response({"value": 1}, "Done")
    assert response == {"success": True, "message": "Done", "data": {"value": 1}, "meta": None}
