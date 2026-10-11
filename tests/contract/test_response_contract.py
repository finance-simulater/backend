"""openapi.yaml에 정의된 엔드포인트의 실제 응답이 스펙 스키마와 일치하는지 검증 (#40).

기존 라우터 테스트(tests/test_credit_router.py 등)와 같은 TestClient + dependency_overrides 목 패턴을
쓰되, 필드값을 손으로 단언하지 않고 assert_response_matches_spec으로 스펙에서 유도한 스키마에 대조한다.
리스트 응답은 빈 배열이면 items 스키마가 검증되지 않으므로 항상 1건 이상 채워서 호출한다.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.credit.model import CreditGradePolicy, CreditHistory
from app.api.v1.credit.router import get_credit_service
from app.api.v1.credit.service import CreditService
from app.api.v1.simulation.model import SimulationState, Turn
from app.api.v1.simulation.router import get_simulation_service
from app.api.v1.simulation.service import SimulationService
from app.api.v1.user.model import User
from app.cache import RedisNotReadyError
from app.health import router as health_router
from app.main import app
from tests.contract.conftest import SpecDict, assert_response_matches_spec

pytestmark = pytest.mark.contract

USER_ID = 1
TURN_CHOICE = {"food_choice": "normal", "shopping_choice": "normal", "leisure_choice": "normal"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.clear()


def _login() -> None:
    app.dependency_overrides[get_current_user] = lambda: User(id=USER_ID, monthly_salary=2_000_000)


def make_state(**overrides) -> SimulationState:
    defaults = dict(
        user_id=USER_ID,
        current_turn=3,
        current_year=2026,
        current_month=3,
        cash_balance=1_000_000,
        credit_score=70,
        consume_score=50,
        status="active",
    )
    defaults.update(overrides)
    state = SimulationState(**defaults)
    state.user = User(id=USER_ID, monthly_salary=2_000_000)
    return state


def make_grade_policy(**overrides) -> CreditGradePolicy:
    defaults = dict(grade="B", grade_rank=6, min_score=65, max_score=74, credit_limit=3_000_000, base_interest_rate=5.5)
    defaults.update(overrides)
    return CreditGradePolicy(**defaults)


def make_turn(**overrides) -> Turn:
    defaults = dict(
        user_id=USER_ID,
        turn_number=2,
        year=2026,
        month=2,
        salary_received=2_000_000,
        fixed_expense_total=500_000,
        variable_expense_total=600_000,
        food_choice="normal",
        shopping_choice="normal",
        leisure_choice="normal",
        consume_score_delta=0,
        credit_score_delta=0,
        loan_repayment_amount=0,
        is_overdue=False,
        cash_balance_after=1_900_000,
        total_asset_after=1_900_000,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Turn(**defaults)


def _override_simulation(state: SimulationState | None, **repositories: MagicMock) -> None:
    """state_repository를 state로 고정한 SimulationService를 주입한다. 나머지 저장소는 기본 MagicMock."""
    state_repository = MagicMock()
    state_repository.find_by_user.return_value = state
    state_repository.save.side_effect = lambda s: s

    credit_repository = MagicMock()
    credit_repository.find_by_score.return_value = make_grade_policy()

    loan_repository = MagicMock()
    loan_repository.find_active_by_user.return_value = None

    stock_repository = MagicMock()
    stock_repository.sum_current_value_by_user.return_value = 0

    fixed_expense_repository = MagicMock()
    fixed_expense_repository.find_all_by_user.return_value = []

    defaults = dict(
        credit_repository=credit_repository,
        loan_repository=loan_repository,
        stock_repository=stock_repository,
        fixed_expense_repository=fixed_expense_repository,
    )
    service = SimulationService(db=MagicMock(), state_repository=state_repository, **{**defaults, **repositories})
    app.dependency_overrides[get_simulation_service] = lambda: service
    _login()


def _override_credit(state: SimulationState | None, **repositories: MagicMock) -> None:
    simulation_repository = MagicMock()
    simulation_repository.find_by_user.return_value = state
    service = CreditService(db=MagicMock(), simulation_repository=simulation_repository, **repositories)
    app.dependency_overrides[get_credit_service] = lambda: service
    _login()


# ── health ──────────────────────────────────────


def test_health(client: TestClient, openapi_spec: SpecDict) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/health", "get")


def test_health_ready(client: TestClient, openapi_spec: SpecDict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_router, "SessionLocal", MagicMock())
    monkeypatch.setattr(health_router, "check_redis", lambda: None)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/health/ready", "get")


def _raise_redis_not_ready() -> None:
    raise RedisNotReadyError("Redis is not ready")


def _db_session_down() -> MagicMock:
    session = MagicMock()
    session.__enter__.return_value.execute.side_effect = OperationalError("SELECT 1", {}, Exception("down"))
    return session


@pytest.mark.parametrize(
    ("session_factory", "redis_check"),
    [
        pytest.param(_db_session_down, lambda: None, id="db-down"),
        pytest.param(MagicMock, _raise_redis_not_ready, id="redis-down"),
    ],
)
def test_health_ready_unavailable(
    client: TestClient, openapi_spec: SpecDict, monkeypatch: pytest.MonkeyPatch, session_factory, redis_check
) -> None:
    monkeypatch.setattr(health_router, "SessionLocal", session_factory)
    monkeypatch.setattr(health_router, "check_redis", redis_check)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert_response_matches_spec(openapi_spec, response, "/health/ready", "get")


# ── simulation ──────────────────────────────────


def test_get_dashboard(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_simulation(make_state())

    response = client.get("/api/v1/simulation")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/simulation", "get")


def test_list_turns(client: TestClient, openapi_spec: SpecDict) -> None:
    turn_repository = MagicMock()
    turn_repository.find_by_user_paginated.return_value = [make_turn(turn_number=2), make_turn(turn_number=1)]
    _override_simulation(make_state(), turn_repository=turn_repository)

    response = client.get("/api/v1/simulation/turns")

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert_response_matches_spec(openapi_spec, response, "/api/v1/simulation/turns", "get")


def test_advance_turn_created(client: TestClient, openapi_spec: SpecDict) -> None:
    def _create_turn(turn: Turn) -> Turn:
        turn.created_at = datetime.now(timezone.utc)  # DB server_default를 흉내
        return turn

    turn_repository = MagicMock()
    turn_repository.create.side_effect = _create_turn
    _override_simulation(make_state(current_turn=1, current_month=1), turn_repository=turn_repository)

    response = client.post("/api/v1/simulation/turns", json=TURN_CHOICE)

    assert response.status_code == 201
    assert_response_matches_spec(openapi_spec, response, "/api/v1/simulation/turns", "post")


def test_advance_turn_conflict_when_completed(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_simulation(make_state(status="completed"))

    response = client.post("/api/v1/simulation/turns", json=TURN_CHOICE)

    assert response.status_code == 409
    assert_response_matches_spec(openapi_spec, response, "/api/v1/simulation/turns", "post")


def test_advance_turn_insufficient_balance(client: TestClient, openapi_spec: SpecDict) -> None:
    # 잔액 0 + 고정지출이 급여를 초과 → 정산 전에 INSUFFICIENT_BALANCE로 거부 (요청 검증 422와는 별개)
    fixed_expense_repository = MagicMock()
    fixed_expense_repository.find_all_by_user.return_value = [MagicMock(amount=5_000_000)]
    _override_simulation(make_state(cash_balance=0), fixed_expense_repository=fixed_expense_repository)

    response = client.post("/api/v1/simulation/turns", json=TURN_CHOICE)

    assert response.status_code == 422
    assert response.json()["code"] == "INSUFFICIENT_BALANCE"
    assert_response_matches_spec(openapi_spec, response, "/api/v1/simulation/turns", "post")


def test_get_turn(client: TestClient, openapi_spec: SpecDict) -> None:
    turn_repository = MagicMock()
    turn_repository.find_by_user_and_turn.return_value = make_turn()
    _override_simulation(make_state(), turn_repository=turn_repository)

    response = client.get("/api/v1/simulation/turns/2")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/simulation/turns/{turn_number}", "get")


def test_get_turn_not_found(client: TestClient, openapi_spec: SpecDict) -> None:
    turn_repository = MagicMock()
    turn_repository.find_by_user_and_turn.return_value = None
    _override_simulation(make_state(), turn_repository=turn_repository)

    response = client.get("/api/v1/simulation/turns/99")

    assert response.status_code == 404
    assert_response_matches_spec(openapi_spec, response, "/api/v1/simulation/turns/{turn_number}", "get")


# ── credit ──────────────────────────────────────


def test_get_credit_score(client: TestClient, openapi_spec: SpecDict) -> None:
    grade_repository = MagicMock()
    grade_repository.find_by_score.return_value = make_grade_policy()
    grade_repository.find_all_ordered.return_value = [
        make_grade_policy(grade="B+", grade_rank=5, min_score=75, max_score=84),
        make_grade_policy(),
    ]
    _override_credit(make_state(), grade_repository=grade_repository)

    response = client.get("/api/v1/credit")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/credit", "get")


def test_get_credit_score_top_grade_has_no_next_grade(client: TestClient, openapi_spec: SpecDict) -> None:
    # 최고 등급(A+)은 다음 등급이 없어 next_grade·score_to_next_grade가 null (spec#10에서 nullable 명시)
    top_grade = make_grade_policy(grade="A+", grade_rank=1, min_score=95, max_score=100)
    grade_repository = MagicMock()
    grade_repository.find_by_score.return_value = top_grade
    grade_repository.find_all_ordered.return_value = [top_grade]
    _override_credit(make_state(credit_score=97), grade_repository=grade_repository)

    response = client.get("/api/v1/credit")

    assert response.status_code == 200
    assert response.json()["next_grade"] is None
    assert_response_matches_spec(openapi_spec, response, "/api/v1/credit", "get")


def test_get_credit_score_not_found(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_credit(None)

    response = client.get("/api/v1/credit")

    assert response.status_code == 404
    assert_response_matches_spec(openapi_spec, response, "/api/v1/credit", "get")


def test_get_credit_history(client: TestClient, openapi_spec: SpecDict) -> None:
    history_repository = MagicMock()
    history_repository.find_by_user_paginated.return_value = [
        CreditHistory(
            id=42,
            user_id=USER_ID,
            turn_number=3,
            delta=1,
            reason="loan_payment",
            score_after=71,
            created_at=datetime.now(timezone.utc),
        )
    ]
    _override_credit(make_state(), history_repository=history_repository)

    response = client.get("/api/v1/credit/history")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/credit/history", "get")


def test_get_credit_history_not_found(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_credit(None)

    response = client.get("/api/v1/credit/history")

    assert response.status_code == 404
    assert_response_matches_spec(openapi_spec, response, "/api/v1/credit/history", "get")
