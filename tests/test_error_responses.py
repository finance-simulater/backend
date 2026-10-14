"""api/domains/errors.md 에 정의된 {"code", "detail"} 응답 형식 검증 (finance-simulater/backend#7)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.user.model import User
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


@pytest.fixture
def logged_in_client(client: TestClient):
    # 요청 검증 단계까지 가려면 인증 의존성을 통과해야 한다 — 검증은 서비스 호출 전에 실패하므로 서비스 목은 불필요
    app.dependency_overrides[get_current_user] = lambda: User(id=1, monthly_salary=2_000_000)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def test_validation_error_detail_lists_loc_and_msg(logged_in_client: TestClient) -> None:
    response = logged_in_client.post("/api/v1/simulation/turns", json={})

    assert response.status_code == 422
    assert response.json() == {
        "code": "INVALID_REQUEST",
        "detail": (
            "body.food_choice: Field required; "
            "body.shopping_choice: Field required; "
            "body.leisure_choice: Field required"
        ),
    }


def test_validation_error_detail_hides_input_and_source_location(logged_in_client: TestClient) -> None:
    # 서버 파일 경로·엔드포인트 함수명·사용자 입력 원본값이 응답에 새지 않아야 한다 (#44)
    payload = {"food_choice": "SECRET_INPUT", "shopping_choice": "normal", "leisure_choice": "normal"}

    response = logged_in_client.post("/api/v1/simulation/turns", json=payload)

    detail = response.json()["detail"]
    assert response.status_code == 422
    assert detail.startswith("body.food_choice: ")
    assert "SECRET_INPUT" not in detail
    assert ".py" not in detail
    assert "advance_turn" not in detail
