"""Contract checks for the modular Polls API."""

import pytest
from pydantic import ValidationError

from app.modules.polls.schemas import PollCommentRequest, PollCreateRequest, PollVoteRequest


def test_poll_requires_two_options() -> None:
    with pytest.raises(ValidationError):
        PollCreateRequest(question="Choose", options=[{"text": "Only one"}])


def test_poll_comment_cannot_be_blank() -> None:
    with pytest.raises(ValidationError):
        PollCommentRequest(comment="  ")


def test_poll_vote_requires_an_option() -> None:
    with pytest.raises(ValidationError):
        PollVoteRequest(option_ids=[])


def test_poll_routes_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.main import app

    paths = app.openapi()["paths"]
    routes = {(method.upper(), path) for path, operations in paths.items() for method in operations}
    expected = {
        ("GET", "/api/polls"),
        ("POST", "/api/polls"),
        ("POST", "/api/admin/polls"),
        ("PUT", "/api/polls/{poll_id}"),
        ("PUT", "/api/admin/polls/{poll_id}"),
        ("DELETE", "/api/polls/{poll_id}"),
        ("DELETE", "/api/admin/polls/{poll_id}"),
        ("POST", "/api/polls/{poll_id}/vote"),
        ("POST", "/api/polls/{poll_id}/like"),
        ("GET", "/api/polls/{poll_id}/comments"),
        ("POST", "/api/polls/{poll_id}/comments"),
    }
    assert expected <= routes
