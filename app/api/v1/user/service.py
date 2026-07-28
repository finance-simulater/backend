from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api.v1.user.model import User
from app.api.v1.user.repository import UserRepository
from app.api.v1.user.schema import UserCreate
from app.core.exceptions import conflict, not_found, unprocessable
from app.core.security import hash_password


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
        normalized_email = str(user_create.email).lower()
        if self.repository.find_by_email(normalized_email) is not None:
            raise conflict("Email already exists", "EMAIL_ALREADY_EXISTS")
        if self.repository.find_by_nickname(user_create.nickname) is not None:
            raise conflict("Nickname already exists", "NICKNAME_ALREADY_EXISTS")

        password_hash = None
        if user_create.provider == "local":
            if user_create.password is None:
                raise unprocessable("Password is required for local signup", "PASSWORD_REQUIRED")
            password_hash = hash_password(user_create.password)

        normalized_user_create = user_create.model_copy(
            update={"email": normalized_email}
        )
        try:
            return self.repository.create(
                normalized_user_create,
                password_hash=password_hash,
            )
        except IntegrityError as exc:
            raise conflict(
                "Email or nickname already exists",
                "USER_ALREADY_EXISTS",
            ) from exc
