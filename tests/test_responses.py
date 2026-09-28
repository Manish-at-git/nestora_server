"""Small unit tests for the shared response utility; database tests come after an isolated test DB is configured."""

from app.core.responses import error_response, success_response


def test_success_response_has_the_fixed_shape() -> None:
    """Every successful endpoint should return the same four outer response fields."""
    response = success_response({"value": 1}, "Done")
    assert response == {"success": True, "message": "Done", "data": {"value": 1}, "meta": None}


def test_error_response_omits_debug_unless_explicitly_enabled() -> None:
    response = error_response("Unable to complete the request.")

    assert response == {
        "success": False,
        "message": "Unable to complete the request.",
        "data": None,
        "meta": None,
    }
    assert "debug" not in response


def test_error_response_includes_debug_only_when_supplied() -> None:
    response = error_response("Unable to complete the request.", debug={"exception_type": "ValueError"})

    assert response["debug"] == {"exception_type": "ValueError"}
