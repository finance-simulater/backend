"""StockHoldingRepository 통합 테스트"""

import pytest

from app.api.v1.stock.repository import StockHoldingRepository
from tests.integration.factories import make_simulation_state, make_user

pytestmark = pytest.mark.integration


def test_create_and_find_by_user_and_type(db_session):
    user = make_user(db_session)
    repository = StockHoldingRepository(db_session)

    holding = repository.create(user.id, "high_vol", 100_000)

    found = repository.find_by_user_and_type(user.id, "high_vol")
    assert found.id == holding.id
    assert repository.find_by_user_and_type(user.id, "low_vol") is None


def test_sum_current_value_by_user_aggregates_holdings(db_session):
    user = make_user(db_session)
    repository = StockHoldingRepository(db_session)
    repository.create(user.id, "high_vol", 100_000)
    repository.create(user.id, "index", 50_000)

    assert repository.sum_current_value_by_user(user.id) == 150_000


def test_sum_current_value_by_user_returns_zero_when_no_holdings(db_session):
    user = make_user(db_session)
    repository = StockHoldingRepository(db_session)

    assert repository.sum_current_value_by_user(user.id) == 0


def test_update_holding_persists_new_values(db_session):
    user = make_user(db_session)
    repository = StockHoldingRepository(db_session)
    holding = repository.create(user.id, "high_vol", 100_000)

    repository.update_holding(holding, principal=100_000, current_value=120_000)

    reloaded = repository.find_by_user_and_type(user.id, "high_vol")
    assert reloaded.current_value == 120_000


def test_delete_holding_removes_row(db_session):
    user = make_user(db_session)
    repository = StockHoldingRepository(db_session)
    holding = repository.create(user.id, "high_vol", 100_000)

    repository.delete_holding(holding)

    assert repository.find_by_user_and_type(user.id, "high_vol") is None


def test_update_cash_balance_persists_on_simulation_state(db_session):
    user = make_user(db_session)
    state = make_simulation_state(db_session, user, cash_balance=1_000_000)
    repository = StockHoldingRepository(db_session)

    repository.update_cash_balance(state, 800_000)

    found = repository.find_simulation_state(user.id)
    assert found.cash_balance == 800_000
