"""Simulation 관련 Repository 통합 테스트"""

import pytest

from app.api.v1.simulation.model import Turn
from app.api.v1.simulation.repository import SimulationStateRepository, TurnRepository
from tests.integration.factories import make_simulation_state, make_user

pytestmark = pytest.mark.integration


def test_simulation_state_save_and_find_by_user(db_session):
    user = make_user(db_session)
    repository = SimulationStateRepository(db_session)

    assert repository.find_by_user(user.id) is None

    state = make_simulation_state(db_session, user, cash_balance=500_000)
    found = repository.find_by_user(user.id)

    assert found.id == state.id
    assert found.cash_balance == 500_000


def make_turn(**overrides) -> dict:
    defaults = dict(
        turn_number=1,
        year=2026,
        month=1,
        salary_received=3_000_000,
        fixed_expense_total=500_000,
        variable_expense_total=300_000,
        food_choice="normal",
        shopping_choice="normal",
        leisure_choice="normal",
        consume_score_delta=0,
        cash_balance_after=2_200_000,
        total_asset_after=2_200_000,
    )
    defaults.update(overrides)
    return defaults


def test_turn_create_and_find_by_user_and_turn(db_session):
    user = make_user(db_session)
    repository = TurnRepository(db_session)

    created = repository.create(Turn(user_id=user.id, **make_turn(turn_number=1)))

    found = repository.find_by_user_and_turn(user.id, 1)
    assert found.id == created.id
    assert repository.find_by_user_and_turn(user.id, 2) is None


def test_turn_find_by_user_paginated_orders_desc_by_turn_number(db_session):
    user = make_user(db_session)
    repository = TurnRepository(db_session)
    for turn_number in range(1, 4):
        repository.create(Turn(user_id=user.id, **make_turn(turn_number=turn_number)))

    first_page = repository.find_by_user_paginated(user.id, cursor=None, size=2)
    assert [turn.turn_number for turn in first_page] == [3, 2]

    second_page = repository.find_by_user_paginated(user.id, cursor=2, size=2)
    assert [turn.turn_number for turn in second_page] == [1]
