"""급여 수정(PATCH /api/v1/users/me) 테스트 (#71)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.user.router import get_user_service
from app.api.v1.user.schema import UserUpdate
from app.api.v1.user.service import UserService
from app.main import app
from tests.auth.factories import make_user


def test_update_me_updates_monthly_salary_of_current_user() -> None:
    repository = MagicMock()
    user = make_user()
    service = UserService(db=MagicMock(), repository=repository)

    service.update_me(user, UserUpdate(monthly_salary=3_500_000))

    repository.update_monthly_salary.assert_called_once_with(user, 3_500_000)


@pytest.fixture
def client() -> TestClient:
    repository = MagicMock()
    repository.update_monthly_salary.side_effect = lambda user, salary: make_user(monthly_salary=salary)
    app.dependency_overrides[get_user_service] = lambda: UserService(db=MagicMock(), repository=repository)
    app.dependency_overrides[get_current_user] = lambda: make_user()
    yield TestClient(app)
    app.dependency_overrides.pop(get_user_service, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_patch_me_returns_updated_user(client: TestClient) -> None:
    response = client.patch("/api/v1/users/me", json={"monthly_salary": 3_500_000})

    assert response.status_code == 200
    assert response.json()["monthly_salary"] == 3_500_000


def test_patch_me_accepts_max_salary(client: TestClient) -> None:
    response = client.patch("/api/v1/users/me", json={"monthly_salary": 50_000_000})

    assert response.status_code == 200


@pytest.mark.parametrize(
    "body",
    [{"monthly_salary": -1}, {}, {"monthly_salary": 50_000_001}],
    ids=["negative", "missing", "over-max"],
)
def test_patch_me_rejects_invalid_salary(client: TestClient, body: dict) -> None:
    response = client.patch("/api/v1/users/me", json=body)

    assert response.status_code == 422
