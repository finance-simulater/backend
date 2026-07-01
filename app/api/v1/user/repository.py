from datetime import datetime

from app.api.v1.user.model import User
from app.api.v1.user.schema import UserCreate


_USERS = [
    User(
        id=1,
        email="alice@example.com",
        nickname="Alice",
        profile_image_seed="alice",
        job_type="employee",
        monthly_salary=3_000_000,
        provider="local",
        is_email_verified=False,
        onboarding_step=0,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
]


class UserRepository:
    def find_all(self) -> list[User]:
        return _USERS

    def find_by_id(self, user_id: int) -> User | None:
        return next((user for user in _USERS if user.id == user_id), None)

    def create(self, user_create: UserCreate) -> User:
        now = datetime.now()
        user = User(
            id=len(_USERS) + 1,
            email=str(user_create.email),
            password=user_create.password,
            nickname=user_create.nickname,
            profile_image_seed=user_create.profile_image_seed,
            job_type=user_create.job_type,
            monthly_salary=user_create.monthly_salary,
            provider=user_create.provider,
            social_id=user_create.social_id,
            is_email_verified=False,
            onboarding_step=0,
            created_at=now,
            updated_at=now,
        )
        _USERS.append(user)
        return user
