"""loan 라우터의 인증/소유자 검증 배선을 확인하는 통합 테스트 (finance-simulater/backend#28).

get_loan/get_schedule/get_loans 세 엔드포인트에 Depends(get_current_user)가
실제로 걸려 있는지, 그리고 소유자가 다른 대출은 404로 응답하는지를
서비스 목(mock)이 아니라 TestClient로 라우팅 경로까지 검증한다.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.loan.model import Loan
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

    assert client.get("/api/v1/loans/").status_code == 401
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


def test_list_loans_scopes_to_current_user() -> None:
    repository = MagicMock()
    repository.find_all_by_user.return_value = [make_loan(loan_id=5, user_id=OWNER_ID)]
    app.dependency_overrides[get_loan_service] = lambda: LoanService(db=MagicMock(), repository=repository)
    app.dependency_overrides[get_current_user] = lambda: User(id=OWNER_ID)

    client = TestClient(app)
    response = client.get("/api/v1/loans/")

    assert response.status_code == 200
    repository.find_all_by_user.assert_called_once_with(OWNER_ID)
