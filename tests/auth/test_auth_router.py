from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt
from fastapi.testclient import TestClient

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.auth.email_verification_service import EmailVerificationResult
from app.api.v1.auth.router import get_auth_service
from app.api.v1.auth.schema import TokenResponse
from app.api.v1.auth.service import AuthResult, AuthService
from app.core.config import settings
from app.main import app
from tests.auth.factories import make_user


def test_login_endpoint_sets_http_only_refresh_cookie(client: TestClient) -> None:
    service = MagicMock(spec=AuthService)
    service.login.return_value = AuthResult(
        user=make_user(),
        tokens=TokenResponse(access_token="access-token", expires_in=900),
        refresh_token="refresh-token",
    )
    app.dependency_overrides[get_auth_service] = lambda: service

    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "access-token",
        "token_type": "bearer",
        "expires_in": 900,
    }
    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=refresh-token" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_verify_email_endpoint_returns_ticket_without_refresh_cookie(
    client: TestClient,
) -> None:
    service = MagicMock(spec=AuthService)
    service.verify_email.return_value = EmailVerificationResult(
        token="v" * 43,
        expires_in=1800,
    )
    app.dependency_overrides[get_auth_service] = lambda: service

    try:
        response = client.post(
            "/api/v1/auth/email/verify",
            json={"email": "user@example.com", "code": "123456"},
        )
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "email_verification_token": "v" * 43,
        "expires_in": 1800,
    }
    assert "set-cookie" not in response.headers


def test_signup_endpoint_sets_refresh_cookie(client: TestClient) -> None:
    service = MagicMock(spec=AuthService)
    service.signup.return_value = AuthResult(
        user=make_user(),
        tokens=TokenResponse(access_token="access-token", expires_in=900),
        refresh_token="refresh-token",
    )
    app.dependency_overrides[get_auth_service] = lambda: service

    try:
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "user@example.com",
                "email_verification_token": "v" * 43,
                "password": "password123",
                "nickname": "tester",
                "profile_image_seed": "tester",
                "job_type": "employee",
                "monthly_salary": 3_000_000,
            },
        )
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 201
    assert response.json()["tokens"]["access_token"] == "access-token"
    assert response.json()["user"]["email"] == "user@example.com"
    assert "refresh_token=refresh-token" in response.headers["set-cookie"]


def test_send_verification_email_endpoint_returns_accepted(
    client: TestClient,
) -> None:
    service = MagicMock(spec=AuthService)
    app.dependency_overrides[get_auth_service] = lambda: service

    try:
        response = client.post(
            "/api/v1/auth/email/send",
            json={"email": "user@example.com"},
        )
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 202
    assert response.json() == {"message": "Verification email has been sent"}
    service.send_verification_email.assert_called_once_with("user@example.com")


def test_refresh_endpoint_requires_cookie(client: TestClient) -> None:
    app.dependency_overrides[get_auth_service] = lambda: MagicMock(spec=AuthService)

    try:
        response = client.post("/api/v1/auth/refresh")
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 401
    assert response.json() == {
        "code": "REFRESH_TOKEN_REQUIRED",
        "detail": "Refresh token is required",
    }


def test_refresh_endpoint_rotates_refresh_cookie(client: TestClient) -> None:
    service = MagicMock(spec=AuthService)
    service.refresh.return_value = AuthResult(
        user=make_user(),
        tokens=TokenResponse(access_token="new-access-token", expires_in=900),
        refresh_token="new-refresh-token",
    )
    app.dependency_overrides[get_auth_service] = lambda: service
    client.cookies.set(
        settings.refresh_cookie_name,
        "old-refresh-token",
        path="/api/v1/auth",
    )

    try:
        response = client.post("/api/v1/auth/refresh")
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access-token"
    service.refresh.assert_called_once_with("old-refresh-token")
    assert "refresh_token=new-refresh-token" in response.headers["set-cookie"]


def test_refresh_endpoint_accepts_expired_access_token_with_valid_cookie(
    client: TestClient,
) -> None:
    expired_access_token = create_expired_access_token()
    service = MagicMock(spec=AuthService)
    service.refresh.return_value = AuthResult(
        user=make_user(),
        tokens=TokenResponse(access_token="new-access-token", expires_in=900),
        refresh_token="new-refresh-token",
    )
    app.dependency_overrides[get_auth_service] = lambda: service
    client.cookies.set(
        settings.refresh_cookie_name,
        "valid-refresh-token",
        path="/api/v1/auth",
    )

    try:
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {expired_access_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access-token"
    service.refresh.assert_called_once_with("valid-refresh-token")


def test_refresh_endpoint_rejects_expired_access_token_without_cookie(
    client: TestClient,
) -> None:
    expired_access_token = create_expired_access_token()
    app.dependency_overrides[get_auth_service] = lambda: MagicMock(spec=AuthService)

    try:
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {expired_access_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 401
    assert response.json()["code"] == "REFRESH_TOKEN_REQUIRED"


def test_logout_revokes_and_deletes_refresh_cookie(client: TestClient) -> None:
    service = MagicMock(spec=AuthService)
    app.dependency_overrides[get_auth_service] = lambda: service
    client.cookies.set(
        settings.refresh_cookie_name,
        "refresh-token",
        path="/api/v1/auth",
    )

    try:
        response = client.post("/api/v1/auth/logout")
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 204
    service.logout.assert_called_once_with("refresh-token")
    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=" in set_cookie
    assert "Max-Age=0" in set_cookie


def test_me_endpoint_requires_access_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "code": "UNAUTHENTICATED",
        "detail": "Authentication is required",
    }


def test_me_endpoint_rejects_expired_access_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {create_expired_access_token()}"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "UNAUTHENTICATED",
        "detail": "Invalid or expired access token",
    }


def test_me_endpoint_returns_current_user(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user()

    try:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer access-token"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def create_expired_access_token() -> str:
    return jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
