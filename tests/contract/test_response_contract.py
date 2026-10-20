"""openapi.yaml에 정의된 엔드포인트의 실제 응답이 스펙 스키마와 일치하는지 검증 (#40).

기존 라우터 테스트(tests/test_credit_router.py 등)와 같은 TestClient + dependency_overrides 목 패턴을
쓰되, 필드값을 손으로 단언하지 않고 assert_response_matches_spec으로 스펙에서 유도한 스키마에 대조한다.
리스트 응답은 빈 배열이면 items 스키마가 검증되지 않으므로 항상 1건 이상 채워서 호출한다.

`created_at`은 실제 DB(MySQL DATETIME)가 돌려주는 것과 같은 naive datetime으로 만든다 —
tz-aware로 만들면 실제보다 깨끗한 데이터로 `date-time` 포맷 위반을 놓친다 (#43).
"""

import re
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.auth.email_verification_service import EmailVerificationResult
from app.api.v1.auth.router import get_auth_service
from app.api.v1.auth.schema import TokenResponse
from app.api.v1.auth.service import AuthResult, AuthService
from app.api.v1.credit.model import CreditGradePolicy, CreditHistory
from app.api.v1.credit.router import get_credit_service
from app.api.v1.credit.service import CreditService
from app.api.v1.fixed_expense.model import FixedExpense
from app.api.v1.fixed_expense.router import get_fixed_expense_service
from app.api.v1.fixed_expense.service import FixedExpenseService
from app.api.v1.loan.model import Loan, RepaymentSchedule
from app.api.v1.loan.router import get_loan_service
from app.api.v1.loan.service import LoanService
from app.api.v1.simulation.model import SimulationState, Turn
from app.api.v1.simulation.router import get_simulation_service
from app.api.v1.simulation.service import SimulationService
from app.api.v1.stock.model import StockHolding
from app.api.v1.stock.router import get_stock_service
from app.api.v1.stock.service import StockService
from app.api.v1.user.model import User
from app.api.v1.user.router import get_user_service
from app.api.v1.user.service import UserService
from app.cache import RedisNotReadyError
from app.core.exceptions import bad_request, conflict, too_many_requests, unauthorized
from app.core.types import MAX_FIXED_EXPENSES
from app.health import router as health_router
from app.main import app
from tests.auth.factories import make_user
from tests.contract.conftest import (
    SPEC_PATH,
    SpecDict,
    assert_response_matches_spec,
    load_openapi_spec,
    spec_operations,
)

pytestmark = pytest.mark.contract

USER_ID = 1
DB_NOW = datetime(2026, 10, 11, 12, 0)  # MySQL DATETIME이 돌려주는 naive 값 (UTC 기준)
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
        created_at=DB_NOW,
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
        turn.created_at = DB_NOW  # DB server_default를 흉내
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
    # 최고 등급(A+)은 다음 등급이 없어 next_grade·score_to_next_grade가 null (spec#10, PR #11 / v0.3.3에서 nullable 명시)
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
            created_at=DB_NOW,
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


# ── auth ────────────────────────────────────────
# AuthService는 Redis·메일 발송에 의존하므로 서비스 자체를 목으로 바꾸고, 라우터의 응답 직렬화만 대조한다.

SIGNUP_BODY = {
    "email": "user@example.com",
    "email_verification_token": "v" * 43,
    "password": "password123",
    "nickname": "tester",
    "profile_image_seed": "tester",
    "job_type": "employee",
    "monthly_salary": 3_000_000,
}
LOGIN_BODY = {"email": "user@example.com", "password": "password123"}


def _override_auth() -> MagicMock:
    service = MagicMock(spec=AuthService)
    app.dependency_overrides[get_auth_service] = lambda: service
    return service


def _auth_result() -> AuthResult:
    return AuthResult(
        user=make_user(created_at=DB_NOW, updated_at=DB_NOW),
        tokens=TokenResponse(access_token="access-token", expires_in=900),
        refresh_token="refresh-token",
    )


def test_send_verification_email(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_auth()

    response = client.post("/api/v1/auth/email/send", json={"email": "user@example.com"})

    assert response.status_code == 202
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/email/send", "post")


def test_send_verification_email_rate_limited(client: TestClient, openapi_spec: SpecDict) -> None:
    service = _override_auth()
    service.send_verification_email.side_effect = too_many_requests("wait", "VERIFICATION_EMAIL_RATE_LIMITED")

    response = client.post("/api/v1/auth/email/send", json={"email": "user@example.com"})

    assert response.status_code == 429
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/email/send", "post")


def test_verify_email(client: TestClient, openapi_spec: SpecDict) -> None:
    service = _override_auth()
    service.verify_email.return_value = EmailVerificationResult(token="v" * 43, expires_in=1800)

    response = client.post("/api/v1/auth/email/verify", json={"email": "user@example.com", "code": "123456"})

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/email/verify", "post")


def test_verify_email_invalid_code(client: TestClient, openapi_spec: SpecDict) -> None:
    service = _override_auth()
    service.verify_email.side_effect = bad_request("invalid", "INVALID_VERIFICATION_CODE")

    response = client.post("/api/v1/auth/email/verify", json={"email": "user@example.com", "code": "000000"})

    assert response.status_code == 400
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/email/verify", "post")


def test_signup(client: TestClient, openapi_spec: SpecDict) -> None:
    service = _override_auth()
    service.signup.return_value = _auth_result()

    response = client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    assert response.status_code == 201
    assert "refresh_token=" in response.headers["set-cookie"]
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/signup", "post")


def test_signup_conflict(client: TestClient, openapi_spec: SpecDict) -> None:
    service = _override_auth()
    service.signup.side_effect = conflict("exists", "EMAIL_ALREADY_EXISTS")

    response = client.post("/api/v1/auth/signup", json=SIGNUP_BODY)

    assert response.status_code == 409
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/signup", "post")


def test_login(client: TestClient, openapi_spec: SpecDict) -> None:
    service = _override_auth()
    service.login.return_value = _auth_result()

    response = client.post("/api/v1/auth/login", json=LOGIN_BODY)

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/login", "post")


def test_login_invalid_credentials(client: TestClient, openapi_spec: SpecDict) -> None:
    service = _override_auth()
    service.login.side_effect = unauthorized("invalid", "INVALID_CREDENTIALS")

    response = client.post("/api/v1/auth/login", json=LOGIN_BODY)

    assert response.status_code == 401
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/login", "post")


def test_refresh(client: TestClient, openapi_spec: SpecDict) -> None:
    service = _override_auth()
    service.refresh.return_value = _auth_result()
    client.cookies.set("refresh_token", "refresh-token")

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/refresh", "post")


def test_refresh_without_cookie(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_auth()

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json()["code"] == "REFRESH_TOKEN_REQUIRED"
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/refresh", "post")


def test_logout(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_auth()

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/logout", "post")


def test_me(client: TestClient, openapi_spec: SpecDict) -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(created_at=DB_NOW, updated_at=DB_NOW)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/auth/me", "get")


# ── investment ──────────────────────────────────


def make_holding(**overrides) -> StockHolding:
    defaults = dict(id=1, user_id=USER_ID, stock_type="high_vol", principal=100_000, current_value=120_000)
    defaults.update(overrides)
    return StockHolding(**defaults)


def _override_stock(state: SimulationState | None, holding: StockHolding | None = None) -> MagicMock:
    repository = MagicMock()
    repository.find_simulation_state.return_value = state
    repository.find_all_by_user.return_value = [holding] if holding else []
    repository.find_by_user_and_type.return_value = holding
    repository.create.side_effect = lambda user_id, stock_type, amount: make_holding(
        stock_type=stock_type, principal=amount, current_value=amount
    )
    repository.update_holding.side_effect = lambda h, principal, current_value: make_holding(
        id=h.id, stock_type=h.stock_type, principal=principal, current_value=current_value
    )
    service = StockService(db=MagicMock(), repository=repository)
    app.dependency_overrides[get_stock_service] = lambda: service
    _login()
    return repository


def test_get_portfolio(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_stock(make_state(), holding=make_holding())

    response = client.get("/api/v1/stocks")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/stocks", "get")


def test_get_portfolio_not_found(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_stock(None)

    response = client.get("/api/v1/stocks")

    assert response.status_code == 404
    assert_response_matches_spec(openapi_spec, response, "/api/v1/stocks", "get")


def test_buy_stock(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_stock(make_state())

    response = client.post("/api/v1/stocks/buy", json={"stock_type": "index", "amount": 50_000})

    assert response.status_code == 201
    assert_response_matches_spec(openapi_spec, response, "/api/v1/stocks/buy", "post")


def test_buy_stock_insufficient_balance(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_stock(make_state(cash_balance=1_000))

    response = client.post("/api/v1/stocks/buy", json={"stock_type": "index", "amount": 50_000})

    assert response.status_code == 422
    assert response.json()["code"] == "INSUFFICIENT_BALANCE"
    assert_response_matches_spec(openapi_spec, response, "/api/v1/stocks/buy", "post")


def test_buy_stock_conflict_when_completed(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_stock(make_state(status="completed"))

    response = client.post("/api/v1/stocks/buy", json={"stock_type": "index", "amount": 50_000})

    assert response.status_code == 409
    assert_response_matches_spec(openapi_spec, response, "/api/v1/stocks/buy", "post")


def test_sell_stock_partial(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_stock(make_state(), holding=make_holding())

    response = client.post("/api/v1/stocks/sell", json={"stock_type": "high_vol", "amount": 20_000})

    assert response.status_code == 200
    assert response.json()["holding"] is not None
    assert_response_matches_spec(openapi_spec, response, "/api/v1/stocks/sell", "post")


def test_sell_stock_all_returns_null_holding(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_stock(make_state(), holding=make_holding())

    response = client.post("/api/v1/stocks/sell", json={"stock_type": "high_vol", "amount": 120_000})

    assert response.status_code == 200
    assert response.json()["holding"] is None
    assert_response_matches_spec(openapi_spec, response, "/api/v1/stocks/sell", "post")


def test_sell_stock_not_held(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_stock(make_state())

    response = client.post("/api/v1/stocks/sell", json={"stock_type": "high_vol", "amount": 1_000})

    assert response.status_code == 404
    assert_response_matches_spec(openapi_spec, response, "/api/v1/stocks/sell", "post")


def test_sell_stock_insufficient_holdings(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_stock(make_state(), holding=make_holding())

    response = client.post("/api/v1/stocks/sell", json={"stock_type": "high_vol", "amount": 999_999})

    assert response.status_code == 422
    assert response.json()["code"] == "INSUFFICIENT_HOLDINGS"
    assert_response_matches_spec(openapi_spec, response, "/api/v1/stocks/sell", "post")


# ── loans ───────────────────────────────────────


def make_loan(**overrides) -> Loan:
    defaults = dict(
        id=5,
        user_id=USER_ID,
        applied_credit_grade="B",
        applied_credit_score=70,
        applied_limit=3_000_000,
        interest_rate=Decimal("5.50"),  # DB NUMERIC(4,2)가 돌려주는 값 — JSON 숫자로 직렬화돼야 한다(#64)
        principal=1_000_000,
        duration_months=6,
        monthly_payment=170_000,
        total_repayment=1_020_000,
        remaining_balance=1_020_000,
        status="active",
        started_turn=1,
        created_at=DB_NOW,
    )
    defaults.update(overrides)
    return Loan(**defaults)


def make_installment(**overrides) -> RepaymentSchedule:
    defaults = dict(loan_id=5, installment_number=1, due_turn=2, amount=170_000, status="pending", paid_at_turn=None)
    defaults.update(overrides)
    return RepaymentSchedule(**defaults)


def _override_loan(
    state: SimulationState | None = None, loan: Loan | None = None, active_loan: Loan | None = None
) -> MagicMock:
    repository = MagicMock()
    repository.find_all_by_user.return_value = [loan] if loan else []
    repository.find_by_id.return_value = loan
    repository.find_active_by_user.return_value = active_loan
    repository.find_schedule_by_loan.return_value = [make_installment(), make_installment(installment_number=2, due_turn=3)]

    def _create_with_schedule(new_loan: Loan, schedule: list[RepaymentSchedule]) -> Loan:
        # DB autoincrement·server_default를 흉내
        new_loan.id, new_loan.status, new_loan.created_at = 7, "active", DB_NOW
        return new_loan

    repository.create_with_schedule.side_effect = _create_with_schedule

    credit_repository = MagicMock()
    credit_repository.find_by_score.return_value = make_grade_policy(base_interest_rate=Decimal("5.50"))
    credit_repository.find_all_ordered.return_value = [
        make_grade_policy(grade="A+", grade_rank=1, min_score=95, max_score=100, base_interest_rate=Decimal("3.00")),
        make_grade_policy(base_interest_rate=Decimal("5.50")),
    ]
    simulation_repository = MagicMock()
    simulation_repository.find_by_user.return_value = state

    service = LoanService(
        db=MagicMock(),
        repository=repository,
        credit_repository=credit_repository,
        simulation_repository=simulation_repository,
    )
    app.dependency_overrides[get_loan_service] = lambda: service
    _login()
    return repository


def test_list_loans(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan(loan=make_loan())

    response = client.get("/api/v1/loans")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans", "get")


def test_get_eligibility(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan(state=make_state())

    response = client.get("/api/v1/loans/eligibility")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/eligibility", "get")


def test_get_eligibility_not_found(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan(state=None)

    response = client.get("/api/v1/loans/eligibility")

    assert response.status_code == 404
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/eligibility", "get")


def test_get_quote(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan(state=make_state())

    response = client.get("/api/v1/loans/quote", params={"principal": 1_000_000, "duration_months": 12})

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/quote", "get")


def test_get_active_loan(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan(active_loan=make_loan())

    response = client.get("/api/v1/loans/active")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/active", "get")


def test_get_active_loan_not_found(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan()

    response = client.get("/api/v1/loans/active")

    assert response.status_code == 404
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/active", "get")


def test_apply_for_loan(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan(state=make_state())

    response = client.post("/api/v1/loans/apply", json={"principal": 1_000_000, "duration_months": 6})

    assert response.status_code == 201
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/apply", "post")


def test_apply_for_loan_already_active(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan(state=make_state(), active_loan=make_loan())

    response = client.post("/api/v1/loans/apply", json={"principal": 1_000_000, "duration_months": 6})

    assert response.status_code == 409
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/apply", "post")


def test_apply_for_loan_limit_exceeded(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan(state=make_state())

    response = client.post("/api/v1/loans/apply", json={"principal": 99_000_000, "duration_months": 6})

    assert response.status_code == 422
    assert response.json()["code"] == "LOAN_LIMIT_EXCEEDED"
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/apply", "post")


def test_get_loan(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan(loan=make_loan())

    response = client.get("/api/v1/loans/5")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/{loan_id}", "get")


def test_get_loan_not_found(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan()

    response = client.get("/api/v1/loans/5")

    assert response.status_code == 404
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/{loan_id}", "get")


def test_get_loan_schedule(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_loan(loan=make_loan())

    response = client.get("/api/v1/loans/5/schedule")

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/loans/{loan_id}/schedule", "get")


# ── users ───────────────────────────────────────

FIXED_EXPENSES_PATH = "/api/v1/users/me/fixed-expenses"
FIXED_EXPENSE_PATH = "/api/v1/users/me/fixed-expenses/{fixed_expense_id}"


def make_fixed_expense(**overrides) -> FixedExpense:
    defaults = dict(id=10, user_id=USER_ID, name="월세", amount=500_000, created_at=DB_NOW, updated_at=DB_NOW)
    defaults.update(overrides)
    return FixedExpense(**defaults)


def _override_fixed_expense(found: FixedExpense | None = None, count: int = 1) -> None:
    repository = MagicMock()
    repository.find_all_by_user.return_value = [make_fixed_expense()]
    repository.count_by_user.return_value = count
    repository.find_by_id.return_value = found
    repository.create.side_effect = lambda user_id, name, amount: make_fixed_expense(
        id=11, user_id=user_id, name=name, amount=amount
    )
    repository.update.side_effect = lambda fixed_expense, changes: fixed_expense
    service = FixedExpenseService(db=MagicMock(), repository=repository)
    app.dependency_overrides[get_fixed_expense_service] = lambda: service
    _login()


def test_update_me(client: TestClient, openapi_spec: SpecDict) -> None:
    repository = MagicMock()
    repository.update_monthly_salary.side_effect = lambda user, salary: make_user(
        monthly_salary=salary, created_at=DB_NOW, updated_at=DB_NOW
    )
    app.dependency_overrides[get_user_service] = lambda: UserService(db=MagicMock(), repository=repository)
    app.dependency_overrides[get_current_user] = lambda: make_user(created_at=DB_NOW, updated_at=DB_NOW)

    response = client.patch("/api/v1/users/me", json={"monthly_salary": 3_500_000})

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, "/api/v1/users/me", "patch")


def test_list_fixed_expenses(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_fixed_expense()

    response = client.get(FIXED_EXPENSES_PATH)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert_response_matches_spec(openapi_spec, response, FIXED_EXPENSES_PATH, "get")


def test_create_fixed_expense(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_fixed_expense()

    response = client.post(FIXED_EXPENSES_PATH, json={"name": "통신비", "amount": 50_000})

    assert response.status_code == 201
    assert_response_matches_spec(openapi_spec, response, FIXED_EXPENSES_PATH, "post")


def test_create_fixed_expense_limit_exceeded(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_fixed_expense(count=MAX_FIXED_EXPENSES)

    response = client.post(FIXED_EXPENSES_PATH, json={"name": "통신비", "amount": 50_000})

    assert response.status_code == 422
    assert response.json()["code"] == "FIXED_EXPENSE_LIMIT_EXCEEDED"
    assert_response_matches_spec(openapi_spec, response, FIXED_EXPENSES_PATH, "post")


def test_update_fixed_expense(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_fixed_expense(found=make_fixed_expense())

    response = client.patch("/api/v1/users/me/fixed-expenses/10", json={"amount": 550_000})

    assert response.status_code == 200
    assert_response_matches_spec(openapi_spec, response, FIXED_EXPENSE_PATH, "patch")


def test_update_fixed_expense_not_found(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_fixed_expense(found=None)

    response = client.patch("/api/v1/users/me/fixed-expenses/10", json={"amount": 550_000})

    assert response.status_code == 404
    assert_response_matches_spec(openapi_spec, response, FIXED_EXPENSE_PATH, "patch")


def test_delete_fixed_expense(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_fixed_expense(found=make_fixed_expense())

    response = client.delete("/api/v1/users/me/fixed-expenses/10")

    assert response.status_code == 204
    assert_response_matches_spec(openapi_spec, response, FIXED_EXPENSE_PATH, "delete")


def test_delete_fixed_expense_of_other_user_returns_404(client: TestClient, openapi_spec: SpecDict) -> None:
    _override_fixed_expense(found=make_fixed_expense(user_id=USER_ID + 1))

    response = client.delete("/api/v1/users/me/fixed-expenses/10")

    assert response.status_code == 404
    assert_response_matches_spec(openapi_spec, response, FIXED_EXPENSE_PATH, "delete")


# ── 공통 에러 응답 (spec#12) ─────────────────────


def _bearer_operations(spec: SpecDict) -> list[tuple[str, str]]:
    """스펙에서 bearerAuth를 요구하는 operation 목록.

    operation에 `security`가 없으면 루트 `security`(bearerAuth)를 따르고, `security: []`(공개)나
    `refreshCookieAuth`만 요구하는 operation은 제외된다. 스펙에서 직접 뽑으므로 새 경로가 추가되면
    자동으로 401 검증 대상에 들어온다.
    """
    default_security = spec.get("security", [])
    return [
        (path, method)
        for path, method, operation in spec_operations(spec)
        if any("bearerAuth" in requirement for requirement in operation.get("security", default_security))
    ]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """401 테스트를 스펙의 bearer operation으로 parametrize한다.

    `@pytest.mark.parametrize(..., _bearer_operations(load_openapi_spec()))`처럼 모듈 import 시점에
    스펙을 읽으면, spec 파일이 없을 때 load_openapi_spec의 skip/fail이 테스트 밖에서 호출돼 수집 오류로
    세션 전체가 중단된다. 여기서는 파일이 없으면 빈 목록으로 parametrize해 이 테스트만 skip되게 두고,
    로컬 skip·CI 실패 판단은 다른 계약 테스트의 openapi_spec fixture에 맡긴다.
    """
    if "bearer_operation" not in metafunc.fixturenames:
        return
    operations = _bearer_operations(load_openapi_spec()) if SPEC_PATH.exists() else []
    metafunc.parametrize("bearer_operation", operations, ids=[f"{method.upper()} {path}" for path, method in operations])


def test_unauthenticated_request_returns_401(
    client: TestClient, openapi_spec: SpecDict, bearer_operation: tuple[str, str]
) -> None:
    path, method = bearer_operation
    # 경로 파라미터는 모두 정수 id라 이름과 무관하게 1로 채운다 — 새 경로 파라미터가 생겨도 그대로 동작한다.
    # 인증 의존성이 body 검증보다 먼저 실패하므로 body는 보내지 않는다.
    url = re.sub(r"\{[^}]+\}", "1", path)

    response = client.request(method, url)

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert_response_matches_spec(openapi_spec, response, path, method)


@pytest.mark.parametrize(
    ("method", "path", "url", "body"),
    [
        ("get", "/api/v1/simulation/turns", "/api/v1/simulation/turns?size=0", None),
        ("post", "/api/v1/simulation/turns", "/api/v1/simulation/turns", {}),
        ("get", "/api/v1/simulation/turns/{turn_number}", "/api/v1/simulation/turns/abc", None),
        ("get", "/api/v1/credit/history", "/api/v1/credit/history?size=101", None),
        ("get", "/api/v1/loans/quote", "/api/v1/loans/quote?principal=1000&duration_months=5", None),
        ("post", "/api/v1/loans/apply", "/api/v1/loans/apply", {"principal": 0, "duration_months": 6}),
        ("get", "/api/v1/loans/{loan_id}", "/api/v1/loans/abc", None),
        ("post", "/api/v1/stocks/buy", "/api/v1/stocks/buy", {"stock_type": "crypto", "amount": 1}),
        ("post", "/api/v1/stocks/sell", "/api/v1/stocks/sell", {"stock_type": "index", "amount": 0}),
        ("post", "/api/v1/auth/login", "/api/v1/auth/login", {"email": "not-an-email", "password": "x"}),
        ("post", "/api/v1/auth/email/verify", "/api/v1/auth/email/verify", {"email": "user@example.com", "code": "12"}),
        ("patch", "/api/v1/users/me", "/api/v1/users/me", {"monthly_salary": -1}),
        ("post", "/api/v1/users/me/fixed-expenses", "/api/v1/users/me/fixed-expenses", {"name": "월세", "amount": 0}),
        (
            "patch",
            "/api/v1/users/me/fixed-expenses/{fixed_expense_id}",
            "/api/v1/users/me/fixed-expenses/1",
            {"amount": 0},
        ),
        ("delete", "/api/v1/users/me/fixed-expenses/{fixed_expense_id}", "/api/v1/users/me/fixed-expenses/abc", None),
    ],
)
def test_invalid_request_returns_422(
    client: TestClient, openapi_spec: SpecDict, method: str, path: str, url: str, body: dict | None
) -> None:
    _login()

    response = client.request(method, url, json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    assert_response_matches_spec(openapi_spec, response, path, method)
