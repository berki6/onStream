"""API key scope mapping (JWT vs machine keys)."""

from src.application.api_key_scopes import (
    JWT_ONLY,
    parse_scopes,
    required_scope,
)
from src.application.error_codes import ErrorCode
from src.application.errors import AppError


def test_required_scope_catalog():
    assert required_scope("GET", "/v1/videos") == "read"
    assert required_scope("POST", "/v1/videos/") == "upload"
    assert required_scope("POST", "/v1/videos/AbCdEfGh/tokens") == "read"
    assert required_scope("DELETE", "/v1/videos/AbCdEfGh") == "write"
    assert required_scope("POST", "/v1/uploads") == "upload"
    assert required_scope("GET", "/v1/webhooks") == "webhooks"
    assert required_scope("POST", "/v1/webhooks") == "webhooks"
    assert required_scope("GET", "/v1/api-keys") == JWT_ONLY
    assert required_scope("POST", "/v1/live") == "write"
    assert required_scope("GET", "/v1/search/capabilities") == "read"
    assert required_scope("GET", "/v1/moderation/queue") == "write"
    assert required_scope("POST", "/v1/moderation/AbCdEfGh/review") == "write"


def test_parse_scopes_rejects_unknown():
    try:
        parse_scopes("read,admin")
        assert False, "expected AppError"
    except AppError as e:
        assert e.code == ErrorCode.API_KEY_BAD_REQUEST
