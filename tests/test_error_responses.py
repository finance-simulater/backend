"""api/domains/errors.md 에 정의된 {"code", "detail"} 응답 형식 검증 (finance-simulater/backend#7)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.user.repository import UserRepository
from app.api.v1.user.router import get_user_service
from app.api.v1.user.service import UserService
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_failure_returns_service_unavailable_code(client: TestClient) -> None:
    with patch("app.health.router.SessionLocal", side_effect=SQLAlchemyError("db down")):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"code": "SERVICE_UNAVAILABLE", "detail": "Database is not ready"}


def test_user_not_found_returns_not_found_code(client: TestClient) -> None:
    fake_repository = MagicMock(spec=UserRepository)
    fake_repository.find_by_id.return_value = None
    app.dependency_overrides[get_user_service] = lambda: UserService(db=MagicMock(), repository=fake_repository)

    try:
        response = client.get("/api/v1/users/999999")
    finally:
        app.dependency_overrides.pop(get_user_service, None)

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "detail": "User not found"}
