from sqlalchemy.orm import Session

from app.api.v1.expense.model import Expense


class ExpenseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_many(self, expenses: list[Expense]) -> list[Expense]:
        self.db.add_all(expenses)
        self.db.commit()
        for expense in expenses:
            self.db.refresh(expense)
        return expenses
