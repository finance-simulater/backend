"""신용점수 조회 API 핵심 로직 테스트 (finance-simulater/backend#27)."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.api.v1 import models  # noqa: F401  (모든 모델을 등록해야 relationship 문자열 참조가 풀린다)
from app.api.v1.credit.model import CreditGradePolicy, CreditHistory
from app.api.v1.credit.service import CreditService
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
    next_grade_policy: CreditGradePolicy | None = None,
    history: list[CreditHistory] | None = None,
) -> CreditService:
    grade_repository = MagicMock()
    grade_repository.find_by_score.return_value = grade_policy
    grade_repository.find_by_rank.return_value = next_grade_policy

    history_repository = MagicMock()
    history_repository.find_by_user_paginated.return_value = history or []

    simulation_repository = MagicMock()
    simulation_repository.find_by_user.return_value = state

    return CreditService(
        db=MagicMock(),
        grade_repository=grade_repository,
        history_repository=history_repository,
        simulation_repository=simulation_repository,
    )


def test_get_score_returns_current_grade_and_next_grade_progress() -> None:
    state = make_state(credit_score=70)
    grade_policy = make_grade_policy()  # B, 65~74
    next_grade_policy = make_grade_policy(grade="B+", grade_rank=5, min_score=75, max_score=84)
    service = make_service(state, grade_policy, next_grade_policy)

    result = service.get_score(1)

    assert result.score == 70
    assert result.grade == "B"
    assert result.credit_limit == 3_000_000
    assert result.next_grade == "B+"
    assert result.score_to_next_grade == 5


def test_get_score_omits_next_grade_at_top_grade() -> None:
    state = make_state(credit_score=98)
    grade_policy = make_grade_policy(grade="A+", grade_rank=1, min_score=95, max_score=100)
    service = make_service(state, grade_policy, next_grade_policy=None)

    result = service.get_score(1)

    assert result.grade == "A+"
    assert result.next_grade is None
    assert result.score_to_next_grade is None


def test_get_score_raises_not_found_when_simulation_state_missing() -> None:
    service = make_service(state=None, grade_policy=make_grade_policy())

    with pytest.raises(AppHTTPException) as exc_info:
        service.get_score(1)

    assert exc_info.value.status_code == 404


def test_get_history_delegates_pagination_to_repository() -> None:
    state = make_state()
    history = [CreditHistory(id=2, user_id=1, turn_number=3, delta=1, reason="loan_payment", score_after=71)]
    service = make_service(state, make_grade_policy(), history=history)

    result = service.get_history(1, cursor=5, size=10)

    assert result == history
    service.history_repository.find_by_user_paginated.assert_called_once_with(1, 5, 10)


def test_get_history_raises_not_found_when_simulation_state_missing() -> None:
    service = make_service(state=None, grade_policy=make_grade_policy())

    with pytest.raises(AppHTTPException) as exc_info:
        service.get_history(1, cursor=None, size=20)

    assert exc_info.value.status_code == 404
