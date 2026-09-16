"""Credit 관련 Repository 통합 테스트

credit_grade_policy는 alembic 마이그레이션이 미리 채워두는 참조 데이터라
팩토리로 새로 만들지 않고 시드된 값을 그대로 사용한다.
"""

import pytest

from app.api.v1.credit.model import CreditHistory
from app.api.v1.credit.repository import CreditGradePolicyRepository, CreditHistoryRepository
from tests.integration.factories import make_user

pytestmark = pytest.mark.integration


def test_find_by_score_returns_matching_grade(db_session):
    repository = CreditGradePolicyRepository(db_session)

    result = repository.find_by_score(70)

    assert result.grade == "B"


def test_find_all_ordered_sorts_by_grade_rank(db_session):
    repository = CreditGradePolicyRepository(db_session)

    result = repository.find_all_ordered()

    assert [policy.grade for policy in result] == [
        "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F+", "F", "F-",
    ]


def test_history_create_and_cursor_pagination(db_session):
    user = make_user(db_session)
    repository = CreditHistoryRepository(db_session)
    for turn in range(1, 4):
        repository.create(
            CreditHistory(
                user_id=user.id,
                turn_number=turn,
                delta=1,
                reason="loan_payment",
                score_after=70 + turn,
            )
        )

    first_page = repository.find_by_user_paginated(user.id, cursor=None, size=2)
    assert [entry.turn_number for entry in first_page] == [3, 2]

    second_page = repository.find_by_user_paginated(user.id, cursor=first_page[-1].id, size=2)
    assert [entry.turn_number for entry in second_page] == [1]
