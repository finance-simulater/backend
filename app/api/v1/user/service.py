from sqlalchemy.orm import Session

from app.api.v1.user.model import User
from app.api.v1.user.repository import UserRepository
from app.api.v1.user.schema import UserUpdate


class UserService:
    def __init__(self, db: Session, repository: UserRepository | None = None) -> None:
        self.repository = repository or UserRepository(db)

    def update_me(self, user: User, request: UserUpdate) -> User:
        # 턴 처리가 매 턴 user.monthly_salary를 새로 읽으므로 다음 턴부터 반영된다
        return self.repository.update_monthly_salary(user, request.monthly_salary)
