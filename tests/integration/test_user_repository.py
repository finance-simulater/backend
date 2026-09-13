"""UserRepository 통합 테스트"""

import pytest

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

    with pytest.raises(Exception):
        repository.create(user_create, password_hash="hashed")
