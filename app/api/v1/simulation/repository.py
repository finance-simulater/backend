from sqlalchemy.orm import Session

from app.api.v1.simulation.model import SimulationState


class SimulationStateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_user(self, user_id: int) -> SimulationState | None:
        return self.db.query(SimulationState).filter(SimulationState.user_id == user_id).first()
