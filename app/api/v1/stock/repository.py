from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.stock.model import StockHolding


class StockHoldingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_all_by_user(self, user_id: int) -> list[StockHolding]:
        return self.db.query(StockHolding).filter(StockHolding.user_id == user_id).all()

    def sum_current_value_by_user(self, user_id: int) -> int:
        total = (
            self.db.query(func.coalesce(func.sum(StockHolding.current_value), 0))
            .filter(StockHolding.user_id == user_id)
            .scalar()
        )
        return int(total)
