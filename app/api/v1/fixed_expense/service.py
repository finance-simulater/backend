from sqlalchemy.orm import Session

from app.api.v1.fixed_expense.model import FixedExpense
from app.api.v1.fixed_expense.repository import FixedExpenseRepository
from app.api.v1.fixed_expense.schema import FixedExpenseCreate, FixedExpenseUpdate
from app.core.exceptions import not_found, unprocessable
from app.core.types import MAX_FIXED_EXPENSES


class FixedExpenseService:
    def __init__(self, db: Session, repository: FixedExpenseRepository | None = None) -> None:
        self.repository = repository or FixedExpenseRepository(db)

    def get_fixed_expenses(self, user_id: int) -> list[FixedExpense]:
        return self.repository.find_all_by_user(user_id)

    def create_fixed_expense(self, user_id: int, request: FixedExpenseCreate) -> FixedExpense:
        # 락 없이 센 뒤 추가하므로 동시 요청이면 상한을 1~2개 넘을 수 있다. INT를 넘으려면 43개가
        # 필요해 허용한다 — 턴 처리의 잔액 검사(INSUFFICIENT_BALANCE)가 기록 전에 한 번 더 막는다.
        if self.repository.count_by_user(user_id) >= MAX_FIXED_EXPENSES:
            raise unprocessable(
                f"고정지출은 최대 {MAX_FIXED_EXPENSES}개까지 등록할 수 있습니다",
                code="FIXED_EXPENSE_LIMIT_EXCEEDED",
            )
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
