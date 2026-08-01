from sqlalchemy.orm import Session

from app.api.v1.fixed_expense.model import FixedExpense


class FixedExpenseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_all_by_user(self, user_id: int) -> list[FixedExpense]:
        return self.db.query(FixedExpense).filter(FixedExpense.user_id == user_id).all()
