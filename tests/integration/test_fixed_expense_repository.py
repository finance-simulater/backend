"""FixedExpenseRepository 통합 테스트 (#71)"""

import pytest

from app.api.v1.fixed_expense.model import FixedExpense
from app.api.v1.fixed_expense.repository import FixedExpenseRepository
from tests.integration.factories import make_user

pytestmark = pytest.mark.integration


def test_create_persists_and_loads_server_defaults(db_session):
    user = make_user(db_session)
    repository = FixedExpenseRepository(db_session)

    created = repository.create(user.id, "월세", 500_000)

    assert created.id is not None
    assert created.created_at is not None
    assert created.updated_at is not None


def test_find_all_by_user_returns_only_own_items_in_insert_order(db_session):
    owner = make_user(db_session, email="owner@example.com", nickname="owner")
    other = make_user(db_session, email="other@example.com", nickname="other")
    repository = FixedExpenseRepository(db_session)
    first = repository.create(owner.id, "월세", 500_000)
    second = repository.create(owner.id, "통신비", 50_000)
    repository.create(other.id, "보험료", 100_000)

    assert [fe.id for fe in repository.find_all_by_user(owner.id)] == [first.id, second.id]


def test_update_changes_given_fields(db_session):
    user = make_user(db_session)
    repository = FixedExpenseRepository(db_session)
    fixed_expense = repository.create(user.id, "월세", 500_000)

    repository.update(fixed_expense, {"amount": 550_000})

    reloaded = db_session.get(FixedExpense, fixed_expense.id)
    assert (reloaded.name, reloaded.amount) == ("월세", 550_000)


def test_delete_removes_row(db_session):
    user = make_user(db_session)
    repository = FixedExpenseRepository(db_session)
    fixed_expense = repository.create(user.id, "월세", 500_000)

    repository.delete(fixed_expense)

    assert repository.find_by_id(fixed_expense.id) is None
