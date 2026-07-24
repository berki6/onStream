"""Structured error envelope and ErrorCode tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.application.error_codes import ERROR_HTTP_STATUS, ErrorCode
from src.application.error_envelope import error_body
from src.application.errors import AppError
from src.main import app
from src.infrastructure.db.session import get_db
from tests.conftest import override_get_db

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_every_error_code_has_http_status():
    for code in ErrorCode:
        assert code in ERROR_HTTP_STATUS, f"Missing HTTP status for {code}"


def test_error_body_shape():
    body = error_body(
        request=None,
        code=ErrorCode.AUTH_UNAUTHORIZED,
        message="nope",
        details=[{"field": "x", "message": "y", "code": "VALIDATION_FAILED"}],
    )
    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_UNAUTHORIZED"
    assert body["error"]["message"] == "nope"
    assert body["api_version"] == "v1"
    assert body["error"]["details"][0]["field"] == "x"


def test_app_error_uses_default_status():
    err = AppError("missing", code=ErrorCode.VIDEO_NOT_FOUND)
    assert err.status_code == 404
    assert err.code is ErrorCode.VIDEO_NOT_FOUND


def test_login_error_envelope():
    response = client.post(
        "/v1/auth/login",
        data={"username": "nope", "password": "wrong"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == ErrorCode.AUTH_INVALID_CREDENTIALS.value
    assert "Incorrect username or password" in body["error"]["message"]
    assert "detail" not in body


def test_validation_error_envelope():
    response = client.post("/v1/auth/register", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == ErrorCode.VALIDATION_FAILED.value
    assert isinstance(body["error"]["details"], list)
    assert "detail" not in body
