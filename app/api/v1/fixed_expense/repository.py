from sqlalchemy.orm import Session

from app.api.v1.fixed_expense.model import FixedExpense


class FixedExpenseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_all_by_user(self, user_id: int) -> list[FixedExpense]:
        return self.db.query(FixedExpense).filter(FixedExpense.user_id == user_id).order_by(FixedExpense.id).all()

    def count_by_user(self, user_id: int) -> int:
        return self.db.query(FixedExpense).filter(FixedExpense.user_id == user_id).count()

    def find_by_id(self, fixed_expense_id: int) -> FixedExpense | None:
        return self.db.query(FixedExpense).filter(FixedExpense.id == fixed_expense_id).first()

    def create(self, user_id: int, name: str, amount: int) -> FixedExpense:
        fixed_expense = FixedExpense(user_id=user_id, name=name, amount=amount)
        self.db.add(fixed_expense)
        self._commit_and_refresh(fixed_expense)
        return fixed_expense

    def update(self, fixed_expense: FixedExpense, changes: dict) -> FixedExpense:
        for field, value in changes.items():
            setattr(fixed_expense, field, value)
        self._commit_and_refresh(fixed_expense)
        return fixed_expense

    def delete(self, fixed_expense: FixedExpense) -> None:
        self.db.delete(fixed_expense)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _commit_and_refresh(self, fixed_expense: FixedExpense) -> None:
        # refresh로 DB가 채운 id·created_at·updated_at(server_default)을 읽어온다
        try:
            self.db.commit()
            self.db.refresh(fixed_expense)
        except Exception:
            self.db.rollback()
            raise
