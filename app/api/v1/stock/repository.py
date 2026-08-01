from sqlalchemy.orm import Session

from app.api.v1.simulation.model import SimulationState
from app.api.v1.stock.model import StockHolding


class StockRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_all_by_user(self, user_id: int) -> list[StockHolding]:
        return (
            self.db.query(StockHolding)
            .filter(StockHolding.user_id == user_id)
            .all()
        )

    def find_by_user_and_type(
        self, user_id: int, stock_type: str, for_update: bool = False
    ) -> StockHolding | None:
        query = self.db.query(StockHolding).filter(
            StockHolding.user_id == user_id,
            StockHolding.stock_type == stock_type,
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def create(self, user_id: int, stock_type: str, amount: int) -> StockHolding:
        holding = StockHolding(
            user_id=user_id,
            stock_type=stock_type,
            principal=amount,
            current_value=amount,
        )
        self.db.add(holding)
        self.db.flush()
        return holding

    def update_holding(self, holding: StockHolding, principal: int, current_value: int) -> StockHolding:
        holding.principal = principal
        holding.current_value = current_value
        self.db.flush()
        return holding

    def delete_holding(self, holding: StockHolding) -> None:
        self.db.delete(holding)
        self.db.flush()

    def find_simulation_state(
        self, user_id: int, for_update: bool = False
    ) -> SimulationState | None:
        query = self.db.query(SimulationState).filter(SimulationState.user_id == user_id)
        if for_update:
            query = query.with_for_update()
        return query.first()

    def update_cash_balance(self, state: SimulationState, new_balance: int) -> None:
        state.cash_balance = new_balance
        self.db.flush()
