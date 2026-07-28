from sqlalchemy.orm import Session

from app.api.v1.user.model import User
from app.api.v1.user.schema import UserCreate


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def find_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def find_by_nickname(self, nickname: str) -> User | None:
        return self.db.query(User).filter(User.nickname == nickname).first()

    def create(
        self,
        user_create: UserCreate,
        password_hash: str | None,
        *,
        is_email_verified: bool = False,
    ) -> User:
        user = User(
            email=str(user_create.email),
            password=password_hash,
            nickname=user_create.nickname,
            profile_image_seed=user_create.profile_image_seed,
            job_type=user_create.job_type,
            monthly_salary=user_create.monthly_salary,
            is_email_verified=is_email_verified,
            provider=user_create.provider,
            social_id=user_create.social_id,
        )
        self.db.add(user)
        try:
            self.db.commit()
            self.db.refresh(user)
        except Exception:
            self.db.rollback()
            raise
        return user
