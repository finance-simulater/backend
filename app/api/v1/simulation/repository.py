from sqlalchemy.orm import Session

from app.api.v1.simulation.model import SimulationState, Turn
from app.core.exceptions import not_found


class SimulationStateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_user(self, user_id: int, for_update: bool = False) -> SimulationState | None:
        query = self.db.query(SimulationState).filter(SimulationState.user_id == user_id)
        if for_update:
            query = query.with_for_update()
        return query.first()

    def save(self, state: SimulationState) -> SimulationState:
        self.db.add(state)
        self.db.flush()
        return state


def get_simulation_state_or_404(
    repository: SimulationStateRepository, user_id: int, for_update: bool = False
) -> SimulationState:
    state = repository.find_by_user(user_id, for_update=for_update)
    if state is None:
        raise not_found("시뮬레이션 정보를 찾을 수 없습니다")
    return state


class TurnRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, turn: Turn) -> Turn:
        self.db.add(turn)
        self.db.flush()
        return turn

    def find_by_user_and_turn(self, user_id: int, turn_number: int) -> Turn | None:
        return (
            self.db.query(Turn)
            .filter(Turn.user_id == user_id, Turn.turn_number == turn_number)
            .first()
        )

    def find_by_user_paginated(self, user_id: int, cursor: int | None, size: int) -> list[Turn]:
        query = self.db.query(Turn).filter(Turn.user_id == user_id)
        if cursor is not None:
            query = query.filter(Turn.turn_number < cursor)
        return query.order_by(Turn.turn_number.desc()).limit(size).all()
