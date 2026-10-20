from sqlalchemy.orm import Session

from app.api.v1.simulation.model import SimulationState
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
        simulation_state: SimulationState | None = None,
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
        # 관계에 붙여 두면 사용자와 같은 커밋으로 INSERT된다 — 상태 없는 사용자가 남지 않는다
        if simulation_state is not None:
            user.simulation_state = simulation_state
        self.db.add(user)
        try:
            self.db.commit()
            self.db.refresh(user)
        except Exception:
            self.db.rollback()
            raise
        return user

    def update_monthly_salary(self, user: User, monthly_salary: int) -> User:
        user.monthly_salary = monthly_salary
        try:
            self.db.commit()
            # updated_at(ON UPDATE CURRENT_TIMESTAMP)을 DB에서 다시 읽는다
            self.db.refresh(user)
        except Exception:
            self.db.rollback()
            raise
        return user
