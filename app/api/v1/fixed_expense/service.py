from sqlalchemy.orm import Session

from app.api.v1.fixed_expense.model import FixedExpense
from app.api.v1.fixed_expense.repository import FixedExpenseRepository
from app.api.v1.fixed_expense.schema import FixedExpenseCreate, FixedExpenseUpdate
from app.core.exceptions import not_found


class FixedExpenseService:
    def __init__(self, db: Session, repository: FixedExpenseRepository | None = None) -> None:
        self.repository = repository or FixedExpenseRepository(db)

    def get_fixed_expenses(self, user_id: int) -> list[FixedExpense]:
        return self.repository.find_all_by_user(user_id)

    def create_fixed_expense(self, user_id: int, request: FixedExpenseCreate) -> FixedExpense:
        return self.repository.create(user_id, request.name, request.amount)

    def update_fixed_expense(self, user_id: int, fixed_expense_id: int, request: FixedExpenseUpdate) -> FixedExpense:
        fixed_expense = self._get_owned_or_404(user_id, fixed_expense_id)
        changes = request.model_dump(exclude_unset=True)
        if not changes:
            return fixed_expense
        return self.repository.update(fixed_expense, changes)

    def delete_fixed_expense(self, user_id: int, fixed_expense_id: int) -> None:
        self.repository.delete(self._get_owned_or_404(user_id, fixed_expense_id))

    def _get_owned_or_404(self, user_id: int, fixed_expense_id: int) -> FixedExpense:
        fixed_expense = self.repository.find_by_id(fixed_expense_id)
        # 존재 여부로 타인의 항목을 추측할 수 없도록 소유자가 달라도 동일하게 404 처리한다 (loan과 동일).
        if fixed_expense is None or fixed_expense.user_id != user_id:
            raise not_found("고정지출 항목을 찾을 수 없습니다")
        return fixed_expense
