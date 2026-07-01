from app.api.v1.user.model import User
from app.api.v1.user.schema import UserCreate


_USERS = [
    User(id=1, name="Alice", email="alice@example.com", age=28),
    User(id=2, name="Bob", email="bob@example.com"),
]


class UserRepository:
    def find_all(self) -> list[User]:
        return _USERS

    def find_by_id(self, user_id: int) -> User | None:
        return next((user for user in _USERS if user.id == user_id), None)

    def create(self, user_create: UserCreate) -> User:
        user = User(
            id=len(_USERS) + 1,
            name=user_create.name,
            email=str(user_create.email),
            age=user_create.age,
        )
        _USERS.append(user)
        return user
