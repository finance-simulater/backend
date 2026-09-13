"""통합 테스트용 최소 데이터 팩토리 (finance-simulater/backend#31).

레포지토리 자체를 검증하는 것이 목적이므로, 의존 데이터(User 등)는
레포지토리를 거치지 않고 모델을 직접 생성/flush 한다.
"""

import uuid

from sqlalchemy.orm import Session

from app.api.v1.simulation.model import SimulationState
from app.api.v1.user.model import User


def make_user(db_session: Session, **overrides) -> User:
    unique = uuid.uuid4().hex[:8]
    defaults = dict(
        email=f"user-{unique}@example.com",
        password="hashed-password",
        nickname=f"user-{unique}",
        profile_image_seed="seed",
        job_type="employee",
        monthly_salary=3_000_000,
    )
    defaults.update(overrides)
    user = User(**defaults)
    db_session.add(user)
    db_session.flush()
    return user


def make_simulation_state(db_session: Session, user: User, **overrides) -> SimulationState:
    defaults = dict(
        user_id=user.id,
        current_turn=1,
        current_year=2026,
        current_month=1,
        cash_balance=1_000_000,
        credit_score=70,
    )
    defaults.update(overrides)
    state = SimulationState(**defaults)
    db_session.add(state)
    db_session.flush()
    return state
