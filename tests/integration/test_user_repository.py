"""UserRepository 통합 테스트"""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.v1.simulation.model import SimulationState
from app.api.v1.simulation.service import new_simulation_state
from app.api.v1.user.model import User
from app.api.v1.user.repository import UserRepository
from app.api.v1.user.schema import UserCreate
from tests.integration.factories import make_user

pytestmark = pytest.mark.integration


def test_create_persists_user_and_defaults(db_session):
    repository = UserRepository(db_session)
    user_create = UserCreate(
        email="new-user@example.com",
        password="password123",
        nickname="new-user",
        profile_image_seed="seed",
        job_type="employee",
        monthly_salary=3_000_000,
    )

    created = repository.create(user_create, password_hash="hashed")

    assert created.id is not None
    assert created.is_email_verified is False
    assert created.provider == "local"

    reloaded = db_session.get(User, created.id)
    assert reloaded is not None
    assert reloaded.email == "new-user@example.com"


def test_create_persists_simulation_state_with_user(db_session):
    repository = UserRepository(db_session)
    user_create = UserCreate(
        email="with-state@example.com",
        password="password123",
        nickname="with-state",
        profile_image_seed="seed",
        job_type="employee",
        monthly_salary=3_000_000,
    )

    created = repository.create(
        user_create,
        password_hash="hashed",
        simulation_state=new_simulation_state(3_000_000, date(2026, 10, 21)),
    )

    state = db_session.query(SimulationState).filter(SimulationState.user_id == created.id).one()
    assert (state.current_turn, state.current_year, state.current_month) == (1, 2026, 11)
    assert (state.cash_balance, state.credit_score, state.consume_score) == (3_000_000, 50, 50)


def test_find_by_email_returns_none_when_missing(db_session):
    repository = UserRepository(db_session)

    assert repository.find_by_email("missing@example.com") is None


def test_find_by_id_and_nickname_return_persisted_user(db_session):
    user = make_user(db_session, nickname="lookup-target")
    repository = UserRepository(db_session)

    assert repository.find_by_id(user.id).id == user.id
    assert repository.find_by_nickname("lookup-target").id == user.id


def test_create_raises_on_duplicate_email(db_session):
    make_user(db_session, email="dup@example.com")
    repository = UserRepository(db_session)
    user_create = UserCreate(
        email="dup@example.com",
        password="password123",
        nickname="another-nickname",
        profile_image_seed="seed",
        job_type="employee",
        monthly_salary=1_000_000,
    )

    with pytest.raises(IntegrityError):
        repository.create(user_create, password_hash="hashed")


def test_update_monthly_salary_persists(db_session):
    user = make_user(db_session, monthly_salary=3_000_000)
    repository = UserRepository(db_session)

    repository.update_monthly_salary(user, 3_500_000)

    assert db_session.get(User, user.id).monthly_salary == 3_500_000
