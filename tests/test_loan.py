"""대출 API 핵심 로직 회귀 테스트 (finance-simulater/backend#14 리팩토링 검증).

get_eligibility/get_quote/apply_for_loan이 공유 함수
(get_simulation_state_or_404, get_grade_policy_or_404)로 교체된 뒤에도
기존 동작(정상 조회, 404 처리)이 그대로인지 확인한다.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.api.v1 import models  # noqa: F401  (모든 모델을 등록해야 relationship 문자열 참조가 풀린다)
from app.api.v1.credit.model import CreditGradePolicy
from app.api.v1.loan.model import Loan
from app.api.v1.loan.service import LoanService
from app.api.v1.simulation.model import SimulationState
from app.core.exceptions import AppHTTPException


def make_grade_policy(**overrides) -> CreditGradePolicy:
    defaults = dict(
        grade="B",
        grade_rank=6,
        min_score=65,
        max_score=74,
        credit_limit=3_000_000,
        base_interest_rate=Decimal("5.5"),
    )
    defaults.update(overrides)
    return CreditGradePolicy(**defaults)


def make_state(**overrides) -> SimulationState:
    defaults = dict(user_id=1, current_turn=3, credit_score=70)
    defaults.update(overrides)
    return SimulationState(**defaults)


def make_service(
    state: SimulationState | None,
    grade_policy: CreditGradePolicy | None,
    active_loan: Loan | None = None,
) -> LoanService:
    repository = MagicMock()
    repository.find_active_by_user.return_value = active_loan
    repository.create_with_schedule.side_effect = lambda loan, schedule: loan

    credit_repository = MagicMock()
    credit_repository.find_by_score.return_value = grade_policy
    credit_repository.find_all_ordered.return_value = [grade_policy] if grade_policy else []

    simulation_repository = MagicMock()
    simulation_repository.find_by_user.return_value = state

    return LoanService(
        db=MagicMock(),
        repository=repository,
        credit_repository=credit_repository,
        simulation_repository=simulation_repository,
    )


def test_get_eligibility_returns_grade_and_limit() -> None:
    state = make_state(credit_score=70)
    grade_policy = make_grade_policy()
    service = make_service(state, grade_policy)

    result = service.get_eligibility(1)

    assert result.credit_grade == "B"
    assert result.credit_score == 70
    assert result.credit_limit == 3_000_000
    assert result.base_interest_rate == Decimal("5.5")


def test_get_eligibility_raises_not_found_when_simulation_state_missing() -> None:
    service = make_service(state=None, grade_policy=make_grade_policy())

    with pytest.raises(AppHTTPException) as exc_info:
        service.get_eligibility(1)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "NOT_FOUND"


def test_get_eligibility_raises_not_found_when_grade_policy_missing() -> None:
    service = make_service(state=make_state(), grade_policy=None)

    with pytest.raises(AppHTTPException) as exc_info:
        service.get_eligibility(1)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "NOT_FOUND"


def test_get_quote_applies_duration_rate_adjustment_and_amortizes_payment() -> None:
    state = make_state(credit_score=70)
    grade_policy = make_grade_policy(base_interest_rate=Decimal("8.0"))
    service = make_service(state, grade_policy)

    # 12개월 -> 기준금리 +2%p = 10.0%
    quote = service.get_quote(1, principal=1_200_000, duration_months=12)

    assert quote.interest_rate == Decimal("10.0")
    assert quote.monthly_payment > 0
    assert quote.total_repayment == quote.monthly_payment * 12
    assert quote.total_interest == quote.total_repayment - 1_200_000


def test_apply_for_loan_rejects_when_active_loan_exists() -> None:
    service = make_service(make_state(), make_grade_policy(), active_loan=Loan(id=1, status="active"))

    with pytest.raises(AppHTTPException) as exc_info:
        service.apply_for_loan(1, principal=500_000, duration_months=6)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "LOAN_ALREADY_ACTIVE"


def test_apply_for_loan_rejects_when_principal_exceeds_limit() -> None:
    service = make_service(make_state(), make_grade_policy(credit_limit=1_000_000))

    with pytest.raises(AppHTTPException) as exc_info:
        service.apply_for_loan(1, principal=2_000_000, duration_months=6)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "LOAN_LIMIT_EXCEEDED"


def test_apply_for_loan_creates_loan_with_schedule() -> None:
    state = make_state(current_turn=3, credit_score=70)
    grade_policy = make_grade_policy(credit_limit=3_000_000)
    service = make_service(state, grade_policy)

    loan = service.apply_for_loan(1, principal=1_000_000, duration_months=6)

    assert loan.principal == 1_000_000
    assert loan.duration_months == 6
    assert loan.applied_credit_grade == "B"
    assert loan.started_turn == 3
    assert loan.remaining_balance == loan.total_repayment


def test_get_active_loan_status_raises_not_found_when_no_active_loan() -> None:
    service = make_service(make_state(), make_grade_policy(), active_loan=None)

    with pytest.raises(AppHTTPException) as exc_info:
        service.get_active_loan_status(1)

    assert exc_info.value.status_code == 404
