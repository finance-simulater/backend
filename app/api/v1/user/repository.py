from sqlalchemy.orm import Session

from app.api.v1.user.model import User
from app.api.v1.user.schema import UserCreate


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_all(self) -> list[User]:
        return self.db.query(User).order_by(User.id).all()

    def find_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def create(self, user_create: UserCreate) -> User:
        user = User(
            email=str(user_create.email),
            password=user_create.password,
            nickname=user_create.nickname,
            profile_image_seed=user_create.profile_image_seed,
            job_type=user_create.job_type,
            monthly_salary=user_create.monthly_salary,
            provider=user_create.provider,
            social_id=user_create.social_id,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
