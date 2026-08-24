"""credit 라우터 통합 테스트 (finance-simulater/backend#27).

서비스 유닛 테스트(tests/test_credit.py)와 별개로, 실제 HTTP 응답 스키마까지
검증한다 — 특히 CreditHistoryEntryResponse에 id가 노출돼 커서 페이지네이션이
실제로 동작하는지를 라우팅 경로를 통해 확인한다.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.credit.model import CreditGradePolicy, CreditHistory
from app.api.v1.credit.router import get_credit_service
from app.api.v1.credit.service import CreditService
from app.api.v1.simulation.model import SimulationState
from app.api.v1.user.model import User
from app.main import app

USER_ID = 1


def make_grade_policy(**overrides) -> CreditGradePolicy:
    defaults = dict(
        grade="B",
        grade_rank=6,
        min_score=65,
        max_score=74,
        credit_limit=3_000_000,
        base_interest_rate=5.5,
    )
    defaults.update(overrides)
    return CreditGradePolicy(**defaults)


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_credit_service, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_requires_authentication() -> None:
    app.dependency_overrides[get_credit_service] = lambda: CreditService(db=MagicMock())

    client = TestClient(app)

    assert client.get("/api/v1/credit").status_code == 401
    assert client.get("/api/v1/credit/history").status_code == 401


def test_get_credit_score_returns_next_grade_progress() -> None:
    grade_policy = make_grade_policy()
    next_grade_policy = make_grade_policy(grade="B+", grade_rank=5, min_score=75, max_score=84)

    grade_repository = MagicMock()
    grade_repository.find_by_score.return_value = grade_policy
    grade_repository.find_all_ordered.return_value = [next_grade_policy, grade_policy]

    simulation_repository = MagicMock()
    simulation_repository.find_by_user.return_value = SimulationState(user_id=USER_ID, credit_score=70)

    service = CreditService(
        db=MagicMock(), grade_repository=grade_repository, simulation_repository=simulation_repository
    )
    app.dependency_overrides[get_credit_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: User(id=USER_ID)

    client = TestClient(app)
    response = client.get("/api/v1/credit")

    assert response.status_code == 200
    assert response.json() == {
        "score": 70,
        "grade": "B",
        "credit_limit": 3_000_000,
        "next_grade": "B+",
        "score_to_next_grade": 5,
    }


def test_get_credit_history_response_exposes_id_for_cursor_pagination() -> None:
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

    simulation_repository = MagicMock()
    simulation_repository.find_by_user.return_value = SimulationState(user_id=USER_ID, credit_score=71)

    service = CreditService(
        db=MagicMock(), history_repository=history_repository, simulation_repository=simulation_repository
    )
    app.dependency_overrides[get_credit_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: User(id=USER_ID)

    client = TestClient(app)
    response = client.get("/api/v1/credit/history")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == 42  # 다음 페이지 요청 시 cursor로 사용할 값
    history_repository.find_by_user_paginated.assert_called_once_with(USER_ID, None, 20)
