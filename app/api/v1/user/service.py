from sqlalchemy.orm import Session

from app.api.v1.user.model import User
from app.api.v1.user.repository import UserRepository
from app.api.v1.user.schema import UserCreate
from app.core.exceptions import not_found


class UserService:
    def __init__(self, db: Session, repository: UserRepository | None = None) -> None:
        self.repository = repository or UserRepository(db)

    def get_users(self) -> list[User]:
        return self.repository.find_all()

    def get_user(self, user_id: int) -> User:
        user = self.repository.find_by_id(user_id)
        if user is None:
            raise not_found("User not found")
        return user

    def create_user(self, user_create: UserCreate) -> User:
        return self.repository.create(user_create)
