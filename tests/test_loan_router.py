"""loan 라우터의 인증/소유자 검증 배선을 확인하는 통합 테스트 (finance-simulater/backend#28).

get_loan/get_schedule/get_loans 세 엔드포인트에 Depends(get_current_user)가
실제로 걸려 있는지, 그리고 소유자가 다른 대출은 404로 응답하는지를
서비스 목(mock)이 아니라 TestClient로 라우팅 경로까지 검증한다.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.loan.model import Loan, RepaymentSchedule
from app.api.v1.loan.router import get_loan_service
from app.api.v1.loan.service import LoanService
from app.api.v1.user.model import User
from app.main import app

OWNER_ID = 1
OTHER_USER_ID = 2


def make_loan(loan_id: int, user_id: int) -> Loan:
    return Loan(
        id=loan_id,
        user_id=user_id,
        applied_credit_grade="B",
        applied_credit_score=70,
        applied_limit=3_000_000,
        interest_rate=5.5,
        principal=1_000_000,
        duration_months=6,
        monthly_payment=170_000,
        total_repayment=1_020_000,
        remaining_balance=1_020_000,
        status="active",
        started_turn=1,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_loan_service, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_requires_authentication() -> None:
    """인증 없이 호출하면 401. (stock·simulation과 동일한 Bearer 규약)"""
    app.dependency_overrides[get_loan_service] = lambda: LoanService(db=MagicMock())

    client = TestClient(app)

    assert client.get("/api/v1/loans").status_code == 401
    assert client.get("/api/v1/loans/1").status_code == 401
    assert client.get("/api/v1/loans/1/schedule").status_code == 401


def test_get_loan_returns_404_for_other_users_loan() -> None:
    repository = MagicMock()
    repository.find_by_id.return_value = make_loan(loan_id=5, user_id=OTHER_USER_ID)
    app.dependency_overrides[get_loan_service] = lambda: LoanService(db=MagicMock(), repository=repository)
    app.dependency_overrides[get_current_user] = lambda: User(id=OWNER_ID)

    client = TestClient(app)

    assert client.get("/api/v1/loans/5").status_code == 404
    assert client.get("/api/v1/loans/5/schedule").status_code == 404


def test_get_loan_returns_200_for_own_loan() -> None:
    repository = MagicMock()
    repository.find_by_id.return_value = make_loan(loan_id=5, user_id=OWNER_ID)
    app.dependency_overrides[get_loan_service] = lambda: LoanService(db=MagicMock(), repository=repository)
    app.dependency_overrides[get_current_user] = lambda: User(id=OWNER_ID)

    client = TestClient(app)
    response = client.get("/api/v1/loans/5")

    assert response.status_code == 200
    assert response.json()["user_id"] == OWNER_ID


def test_get_schedule_returns_200_with_serialized_items_for_own_loan() -> None:
    repository = MagicMock()
    repository.find_by_id.return_value = make_loan(loan_id=5, user_id=OWNER_ID)
    repository.find_schedule_by_loan.return_value = [
        RepaymentSchedule(
            id=1,
            loan_id=5,
            installment_number=1,
            due_turn=2,
            amount=170_000,
            status="pending",
            paid_at_turn=None,
            created_at=datetime.now(timezone.utc),
        )
    ]
    app.dependency_overrides[get_loan_service] = lambda: LoanService(db=MagicMock(), repository=repository)
    app.dependency_overrides[get_current_user] = lambda: User(id=OWNER_ID)

    client = TestClient(app)
    response = client.get("/api/v1/loans/5/schedule")

    assert response.status_code == 200
    assert response.json() == [
        {
            "installment_number": 1,
            "due_turn": 2,
            "amount": 170_000,
            "status": "pending",
            "paid_at_turn": None,
        }
    ]


def test_list_loans_scopes_to_current_user() -> None:
    repository = MagicMock()
    repository.find_all_by_user.return_value = [make_loan(loan_id=5, user_id=OWNER_ID)]
    app.dependency_overrides[get_loan_service] = lambda: LoanService(db=MagicMock(), repository=repository)
    app.dependency_overrides[get_current_user] = lambda: User(id=OWNER_ID)

    client = TestClient(app)
    response = client.get("/api/v1/loans")

    assert response.status_code == 200
    repository.find_all_by_user.assert_called_once_with(OWNER_ID)


@pytest.mark.parametrize("duration_months", [3, 6, 12])
def test_get_quote_accepts_duration_from_query_string(duration_months: int) -> None:
    """쿼리 문자열("12")로 들어온 기간이 Literal 검증에 막혀 항상 422가 나던 버그 (#67)."""
    simulation_repository = MagicMock()
    simulation_repository.find_by_user.return_value = MagicMock(credit_score=70)
    credit_repository = MagicMock()
    credit_repository.find_by_score.return_value = MagicMock(base_interest_rate=Decimal("5.5"))
    app.dependency_overrides[get_loan_service] = lambda: LoanService(
        db=MagicMock(), credit_repository=credit_repository, simulation_repository=simulation_repository
    )
    app.dependency_overrides[get_current_user] = lambda: User(id=OWNER_ID)

    client = TestClient(app)
    response = client.get("/api/v1/loans/quote", params={"principal": 1_000_000, "duration_months": duration_months})

    assert response.status_code == 200
    assert response.json()["duration_months"] == duration_months


def test_get_quote_rejects_unsupported_duration() -> None:
    app.dependency_overrides[get_loan_service] = lambda: LoanService(db=MagicMock())
    app.dependency_overrides[get_current_user] = lambda: User(id=OWNER_ID)

    client = TestClient(app)
    response = client.get("/api/v1/loans/quote", params={"principal": 1_000_000, "duration_months": 5})

    assert response.status_code == 422


@pytest.mark.parametrize(("duration_months", "expected_status"), [(6, 201), (5, 422)])
def test_apply_validates_duration_with_shared_loan_duration(duration_months: int, expected_status: int) -> None:
    """신청 body도 견적 쿼리와 같은 LoanDuration으로 검증한다 (#67)."""
    repository = MagicMock()
    repository.find_active_by_user.return_value = None
    repository.create_with_schedule.side_effect = lambda loan, schedule: make_loan(loan_id=7, user_id=OWNER_ID)
    simulation_repository = MagicMock()
    simulation_repository.find_by_user.return_value = MagicMock(credit_score=70, current_turn=1)
    credit_repository = MagicMock()
    credit_repository.find_by_score.return_value = MagicMock(
        grade="B", credit_limit=3_000_000, base_interest_rate=Decimal("5.5")
    )
    app.dependency_overrides[get_loan_service] = lambda: LoanService(
        db=MagicMock(),
        repository=repository,
        credit_repository=credit_repository,
        simulation_repository=simulation_repository,
    )
    app.dependency_overrides[get_current_user] = lambda: User(id=OWNER_ID)

    client = TestClient(app)
    response = client.post("/api/v1/loans/apply", json={"principal": 1_000_000, "duration_months": duration_months})

    assert response.status_code == expected_status
