"""simulation 라우터의 요청/응답 스키마 직렬화 검증 (get_state, advance_turn)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.credit.model import CreditGradePolicy
from app.api.v1.simulation.model import SimulationState
from app.api.v1.simulation.router import get_simulation_service
from app.api.v1.simulation.service import SimulationService
from app.api.v1.user.model import User
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _override(service: SimulationService):
    app.dependency_overrides[get_simulation_service] = lambda: service


def test_get_dashboard_returns_serialized_state(client: TestClient) -> None:
    state = SimulationState(
        user_id=1,
        current_turn=3,
        current_year=2026,
        current_month=3,
        cash_balance=1_000_000,
        credit_score=52,
        consume_score=48,
        status="active",
    )
    state_repository = MagicMock()
    state_repository.find_by_user.return_value = state

    credit_repository = MagicMock()
    credit_repository.find_by_score.return_value = CreditGradePolicy(
        grade="C", grade_rank=8, min_score=50, max_score=54, credit_limit=1_000_000, base_interest_rate=8.5
    )

    loan_repository = MagicMock()
    loan_repository.find_active_by_user.return_value = None

    stock_repository = MagicMock()
    stock_repository.sum_current_value_by_user.return_value = 0

    service = SimulationService(
        db=MagicMock(),
        state_repository=state_repository,
        credit_repository=credit_repository,
        loan_repository=loan_repository,
        stock_repository=stock_repository,
    )
    _override(service)

    try:
        response = client.get("/api/v1/simulation/users/1")
    finally:
        app.dependency_overrides.pop(get_simulation_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["current_turn"] == 3
    assert body["cash_balance"] == 1_000_000
    assert body["credit_grade"] == "C"
    assert body["has_active_loan"] is False
    assert body["status"] == "active"


def test_advance_turn_returns_created_turn(client: TestClient) -> None:
    state = SimulationState(
        user_id=1,
        current_turn=1,
        current_year=2026,
        current_month=1,
        cash_balance=1_000_000,
        credit_score=50,
        consume_score=50,
        status="active",
    )
    state.user = User(id=1, monthly_salary=2_000_000)

    state_repository = MagicMock()
    state_repository.find_by_user.return_value = state
    state_repository.save.side_effect = lambda s: s

    def _create_turn(turn):
        turn.created_at = datetime.now(timezone.utc)
        return turn

    turn_repository = MagicMock()
    turn_repository.create.side_effect = _create_turn

    fixed_expense_repository = MagicMock()
    fixed_expense_repository.find_all_by_user.return_value = []

    expense_repository = MagicMock()

    loan_repository = MagicMock()
    loan_repository.find_active_by_user.return_value = None

    stock_repository = MagicMock()
    stock_repository.sum_current_value_by_user.return_value = 0

    service = SimulationService(
        db=MagicMock(),
        state_repository=state_repository,
        turn_repository=turn_repository,
        fixed_expense_repository=fixed_expense_repository,
        expense_repository=expense_repository,
        loan_repository=loan_repository,
        stock_repository=stock_repository,
    )
    _override(service)

    try:
        response = client.post(
            "/api/v1/simulation/users/1/turns",
            json={"food_choice": "normal", "shopping_choice": "normal", "leisure_choice": "normal"},
        )
    finally:
        app.dependency_overrides.pop(get_simulation_service, None)

    assert response.status_code == 201
    body = response.json()
    assert body["turn_number"] == 1
    assert body["salary_received"] == 2_000_000
    assert body["is_overdue"] is False
    assert "created_at" in body
