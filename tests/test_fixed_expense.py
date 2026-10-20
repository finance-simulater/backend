"""고정지출 CRUD 서비스·라우터 테스트 (#71)."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.fixed_expense.model import FixedExpense
from app.api.v1.fixed_expense.router import get_fixed_expense_service
from app.api.v1.fixed_expense.schema import FixedExpenseCreate, FixedExpenseUpdate
from app.api.v1.fixed_expense.service import FixedExpenseService
from app.api.v1.user.model import User
from app.core.exceptions import AppHTTPException
from app.main import app

OWNER_ID = 1
OTHER_USER_ID = 2
NOW = datetime(2026, 10, 21, 12, 0)


def make_fixed_expense(**overrides) -> FixedExpense:
    defaults = dict(id=10, user_id=OWNER_ID, name="월세", amount=500_000, created_at=NOW, updated_at=NOW)
    defaults.update(overrides)
    return FixedExpense(**defaults)


def make_service(found: FixedExpense | None = None) -> tuple[FixedExpenseService, MagicMock]:
    repository = MagicMock()
    repository.find_by_id.return_value = found
    repository.update.side_effect = lambda fixed_expense, changes: fixed_expense
    repository.create.side_effect = lambda user_id, name, amount: make_fixed_expense(name=name, amount=amount)
    return FixedExpenseService(db=MagicMock(), repository=repository), repository


# ── service ─────────────────────────────────────


def test_create_passes_name_and_amount() -> None:
    service, repository = make_service()

    service.create_fixed_expense(OWNER_ID, FixedExpenseCreate(name="통신비", amount=50_000))

    repository.create.assert_called_once_with(OWNER_ID, "통신비", 50_000)


def test_update_changes_only_sent_fields() -> None:
    service, repository = make_service(found=make_fixed_expense())

    service.update_fixed_expense(OWNER_ID, 10, FixedExpenseUpdate(amount=600_000))

    repository.update.assert_called_once()
    assert repository.update.call_args.args[1] == {"amount": 600_000}


def test_name_is_stripped_before_saving() -> None:
    service, repository = make_service(found=make_fixed_expense())

    service.create_fixed_expense(OWNER_ID, FixedExpenseCreate(name="  통신비 ", amount=50_000))
    service.update_fixed_expense(OWNER_ID, 10, FixedExpenseUpdate(name=" 관리비  "))

    repository.create.assert_called_once_with(OWNER_ID, "통신비", 50_000)
    assert repository.update.call_args.args[1] == {"name": "관리비"}


def test_update_ignores_fields_not_sent() -> None:
    service, repository = make_service(found=make_fixed_expense())

    service.update_fixed_expense(OWNER_ID, 10, FixedExpenseUpdate.model_validate({"name": "관리비"}))

    assert repository.update.call_args.args[1] == {"name": "관리비"}


def test_update_with_empty_body_returns_current_without_writing() -> None:
    current = make_fixed_expense()
    service, repository = make_service(found=current)

    assert service.update_fixed_expense(OWNER_ID, 10, FixedExpenseUpdate()) is current
    repository.update.assert_not_called()


@pytest.mark.parametrize("found", [None, make_fixed_expense(user_id=OTHER_USER_ID)], ids=["missing", "other-user"])
def test_update_and_delete_return_404_for_missing_or_other_users_item(found: FixedExpense | None) -> None:
    service, repository = make_service(found=found)

    for call in (
        lambda: service.update_fixed_expense(OWNER_ID, 10, FixedExpenseUpdate(amount=1)),
        lambda: service.delete_fixed_expense(OWNER_ID, 10),
    ):
        with pytest.raises(AppHTTPException) as exc_info:
            call()
        assert exc_info.value.status_code == 404

    repository.update.assert_not_called()
    repository.delete.assert_not_called()


def test_delete_removes_owned_item() -> None:
    owned = make_fixed_expense()
    service, repository = make_service(found=owned)

    service.delete_fixed_expense(OWNER_ID, 10)

    repository.delete.assert_called_once_with(owned)


# ── router ──────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    service, _ = make_service(found=make_fixed_expense())
    app.dependency_overrides[get_fixed_expense_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: User(id=OWNER_ID)
    yield TestClient(app)
    app.dependency_overrides.pop(get_fixed_expense_service, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize(
    "body",
    [
        {"name": "월세", "amount": 0},
        {"name": "", "amount": 1_000},
        {"name": "x" * 51, "amount": 1_000},
        {"amount": 1_000},
        {"name": "월세", "amount": 50_000_001},
        {"name": "   ", "amount": 1_000},
    ],
    ids=["amount-zero", "empty-name", "name-too-long", "missing-name", "amount-over-max", "blank-name"],
)
def test_create_rejects_invalid_body(client: TestClient, body: dict) -> None:
    response = client.post("/api/v1/users/me/fixed-expenses", json=body)

    assert response.status_code == 422


def test_create_accepts_max_amount(client: TestClient) -> None:
    response = client.post("/api/v1/users/me/fixed-expenses", json={"name": "월세", "amount": 50_000_000})

    assert response.status_code == 201


@pytest.mark.parametrize(
    "body",
    [{"amount": 0}, {"amount": 50_000_001}, {"amount": None}, {"name": None}, {"name": "   "}],
    ids=["amount-zero", "amount-over-max", "null-amount", "null-name", "blank-name"],
)
def test_update_rejects_invalid_body(client: TestClient, body: dict) -> None:
    # 명시적 null은 "값 삭제"로 오해되지 않도록 무시하지 않고 422로 거절한다 (spec#19)
    response = client.patch("/api/v1/users/me/fixed-expenses/10", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_update_null_error_message_does_not_echo_input(client: TestClient) -> None:
    response = client.patch("/api/v1/users/me/fixed-expenses/10", json={"amount": None})

    assert response.json()["detail"].startswith("body.amount: ")
    assert "None" not in response.json()["detail"]


def test_delete_returns_204(client: TestClient) -> None:
    response = client.delete("/api/v1/users/me/fixed-expenses/10")

    assert response.status_code == 204
    assert response.content == b""
