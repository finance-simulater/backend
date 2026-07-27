from sqlalchemy.orm import Session

from app.api.v1.simulation.model import SimulationState, Turn


class SimulationStateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_user(self, user_id: int) -> SimulationState | None:
        return self.db.query(SimulationState).filter(SimulationState.user_id == user_id).first()

    def save(self, state: SimulationState) -> SimulationState:
        self.db.add(state)
        self.db.commit()
        self.db.refresh(state)
        return state


class TurnRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, turn: Turn) -> Turn:
        self.db.add(turn)
        self.db.commit()
        self.db.refresh(turn)
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
