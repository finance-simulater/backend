"""턴 진행 동시 요청 시나리오 동시성 테스트

`advance_turn`은 `get_simulation_state_or_404(..., for_update=True)`로 유저의
simulation_state row를 잠그고 시작한다. 두 요청이 동시에 들어오면 DB row lock이
뒤 요청을 블로킹시켜 순차적으로 처리되어야 하고(lost update 없음), 둘 다
성공해야 한다 — 이 회귀를 검증한다.
"""

import pytest

from app.api.v1.simulation.repository import SimulationStateRepository
from app.api.v1.simulation.schema import TurnChoiceRequest
from app.api.v1.simulation.service import SimulationService
from tests.integration.concurrency import run_concurrently
from tests.integration.factories import make_simulation_state, make_user

pytestmark = pytest.mark.integration


def test_advance_turn_concurrent_requests_do_not_lose_update(real_session_factory):
    session_factory, created_user_ids = real_session_factory

    setup_session = session_factory()
    user = make_user(setup_session, monthly_salary=3_000_000)
    make_simulation_state(setup_session, user, cash_balance=5_000_000, credit_score=70)
    setup_session.commit()
    created_user_ids.append(user.id)
    user_id = user.id
    setup_session.close()

    choice = TurnChoiceRequest(food_choice="normal", shopping_choice="normal", leisure_choice="normal")

    def advance() -> int:
        session = session_factory()
        try:
            turn = SimulationService(session).advance_turn(user_id, choice)
            return turn.turn_number
        finally:
            session.close()

    results = run_concurrently(advance, advance)

    failures = [r for r in results if isinstance(r, Exception)]
    assert failures == []
    # row lock 덕분에 두 요청이 같은 turn_number를 덮어쓰지 않고 1, 2로 순차 처리된다.
    assert sorted(results) == [1, 2]

    verify_session = session_factory()
    try:
        state = SimulationStateRepository(verify_session).find_by_user(user_id)
    finally:
        verify_session.close()

    assert state.current_turn == 3
