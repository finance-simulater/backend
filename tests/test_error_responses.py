"""api/domains/errors.md 에 정의된 {"code", "detail"} 응답 형식 검증 (finance-simulater/backend#7)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.cache import RedisNotReadyError
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def client_without_server_exceptions() -> TestClient:
    # 미처리 예외 핸들러 검증용 — 기본 TestClient는 서버 예외를 테스트 프로세스로 그대로 re-raise한다.
    return TestClient(app, raise_server_exceptions=False)


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_failure_returns_service_unavailable_code(client: TestClient) -> None:
    with patch("app.health.router.SessionLocal", side_effect=SQLAlchemyError("db down")):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"code": "SERVICE_UNAVAILABLE", "detail": "Database is not ready"}


def test_health_ready_success_returns_ready(client: TestClient) -> None:
    with (
        patch("app.health.router.SessionLocal") as session_local,
        patch("app.health.router.check_redis"),
    ):
        db = session_local.return_value.__enter__.return_value
        db.execute.return_value = None

        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_health_ready_redis_failure_returns_service_unavailable_code(client: TestClient) -> None:
    with (
        patch("app.health.router.SessionLocal") as session_local,
        patch("app.health.router.check_redis", side_effect=RedisNotReadyError("redis down")),
    ):
        db = session_local.return_value.__enter__.return_value
        db.execute.return_value = None

        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"code": "SERVICE_UNAVAILABLE", "detail": "Redis is not ready"}


def test_unhandled_exception_returns_internal_error_code(
    client_without_server_exceptions: TestClient,
) -> None:
    with patch("app.health.router.SessionLocal", side_effect=RuntimeError("unexpected bug")):
        response = client_without_server_exceptions.get("/health/ready")

    assert response.status_code == 500
    assert response.json() == {"code": "INTERNAL_ERROR", "detail": "Internal server error"}


@pytest.mark.parametrize("method", ["get", "post"])
def test_public_user_management_endpoints_are_not_exposed(
    client: TestClient,
    method: str,
) -> None:
    response = getattr(client, method)("/api/v1/users/")

    assert response.status_code == 404
