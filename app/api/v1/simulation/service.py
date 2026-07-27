from datetime import date

from sqlalchemy.orm import Session

from app.api.v1.credit.model import CreditHistory
from app.api.v1.credit.repository import CreditGradePolicyRepository, CreditHistoryRepository
from app.api.v1.expense.model import Expense
from app.api.v1.expense.repository import ExpenseRepository
from app.api.v1.fixed_expense.repository import FixedExpenseRepository
from app.api.v1.loan.repository import LoanRepository
from app.api.v1.simulation.model import SimulationState, Turn
from app.api.v1.simulation.repository import SimulationStateRepository, TurnRepository
from app.api.v1.simulation.schema import ConsumeLevel, SimulationStateResponse, TurnChoiceRequest
from app.api.v1.stock.repository import StockHoldingRepository
from app.api.v1.user.repository import UserRepository
from app.core.exceptions import conflict, not_found

# 소비체크 수준별 지출액 = 월급 대비 % (카테고리 3개 각각 독립 적용)
CONSUME_LEVEL_EXPENSE_RATIO: dict[ConsumeLevel, int] = {
    "save": 5,
    "normal": 10,
    "some": 18,
    "much": 30,
}

# 소비체크 수준별 소비점수 변동(카테고리당, 3개 합산 후 clamp)
CONSUME_LEVEL_SCORE_DELTA: dict[ConsumeLevel, int] = {
    "save": 2,
    "normal": 0,
    "some": -2,
    "much": -5,
}

CATEGORY_LABELS = {
    "food_choice": "식비",
    "shopping_choice": "쇼핑",
    "leisure_choice": "여가",
}


class SimulationService:
    def __init__(
        self,
        db: Session,
        state_repository: SimulationStateRepository | None = None,
        turn_repository: TurnRepository | None = None,
        user_repository: UserRepository | None = None,
        fixed_expense_repository: FixedExpenseRepository | None = None,
        expense_repository: ExpenseRepository | None = None,
        loan_repository: LoanRepository | None = None,
        credit_repository: CreditGradePolicyRepository | None = None,
        credit_history_repository: CreditHistoryRepository | None = None,
        stock_repository: StockHoldingRepository | None = None,
    ) -> None:
        self.state_repository = state_repository or SimulationStateRepository(db)
        self.turn_repository = turn_repository or TurnRepository(db)
        self.user_repository = user_repository or UserRepository(db)
        self.fixed_expense_repository = fixed_expense_repository or FixedExpenseRepository(db)
        self.expense_repository = expense_repository or ExpenseRepository(db)
        self.loan_repository = loan_repository or LoanRepository(db)
        self.credit_repository = credit_repository or CreditGradePolicyRepository(db)
        self.credit_history_repository = credit_history_repository or CreditHistoryRepository(db)
        self.stock_repository = stock_repository or StockHoldingRepository(db)

    def get_state(self, user_id: int) -> SimulationStateResponse:
        state = self._get_state(user_id)
        stock_value_total = self._stock_value_total(user_id)
        total_asset = state.cash_balance + stock_value_total
        grade_policy = self.credit_repository.find_by_score(state.credit_score)
        return SimulationStateResponse(
            current_turn=state.current_turn,
            current_year=state.current_year,
            current_month=state.current_month,
            cash_balance=state.cash_balance,
            total_asset=total_asset,
            stock_ratio=(stock_value_total / total_asset) if total_asset else 0.0,
            credit_score=state.credit_score,
            credit_grade=grade_policy.grade if grade_policy else None,
            consume_score=state.consume_score,
            has_active_loan=self.loan_repository.find_active_by_user(user_id) is not None,
            status=state.status,
        )

    def list_turns(self, user_id: int, cursor: int | None, size: int) -> list[Turn]:
        self._get_state(user_id)
        return self.turn_repository.find_by_user_paginated(user_id, cursor, size)

    def get_turn(self, user_id: int, turn_number: int) -> Turn:
        turn = self.turn_repository.find_by_user_and_turn(user_id, turn_number)
        if turn is None:
            raise not_found("해당 턴을 찾을 수 없습니다", code="TURN_NOT_FOUND")
        return turn

    def advance_turn(self, user_id: int, choice: TurnChoiceRequest) -> Turn:
        state = self._get_state(user_id)
        if state.status != "active":
            raise conflict("이미 완료된 시뮬레이션입니다", code="SIMULATION_ALREADY_COMPLETED")

        user = self.user_repository.find_by_id(user_id)
        if user is None:
            raise not_found("사용자를 찾을 수 없습니다")

        turn_number = state.current_turn
        year, month = state.current_year, state.current_month
        expense_date = date(year, month, 1)

        salary_received = user.monthly_salary

        fixed_expenses = self.fixed_expense_repository.find_all_by_user(user_id)
        fixed_expense_total = sum(fe.amount for fe in fixed_expenses)
        new_expenses = [
            Expense(
                user_id=user_id,
                turn_number=turn_number,
                name=fe.name,
                amount=fe.amount,
                expense_type="fixed",
                expense_date=expense_date,
            )
            for fe in fixed_expenses
        ]

        variable_expense_total = 0
        consume_score_delta = 0
        for field, label in CATEGORY_LABELS.items():
            level: ConsumeLevel = getattr(choice, field)
            amount = (salary_received * CONSUME_LEVEL_EXPENSE_RATIO[level]) // 100
            variable_expense_total += amount
            consume_score_delta += CONSUME_LEVEL_SCORE_DELTA[level]
            new_expenses.append(
                Expense(
                    user_id=user_id,
                    turn_number=turn_number,
                    name=label,
                    amount=amount,
                    expense_type="variable",
                    expense_date=expense_date,
                )
            )
        if new_expenses:
            self.expense_repository.create_many(new_expenses)

        consume_score = self._clamp(state.consume_score + consume_score_delta)

        cash_balance = state.cash_balance + salary_received - fixed_expense_total - variable_expense_total

        loan_repayment_amount = 0
        is_overdue = False
        credit_score = state.credit_score
        loan = self.loan_repository.find_active_by_user(user_id)
        if loan is not None:
            installment = self.loan_repository.find_pending_installment(loan.id, turn_number)
            if installment is not None:
                if cash_balance >= installment.amount:
                    cash_balance -= installment.amount
                    loan_repayment_amount = installment.amount
                    installment.status = "paid"
                    installment.paid_at_turn = turn_number
                    loan.remaining_balance -= installment.amount

                    credit_score = self._clamp(credit_score + 1)
                    self.credit_history_repository.create(
                        CreditHistory(
                            user_id=user_id,
                            turn_number=turn_number,
                            delta=1,
                            reason="loan_payment",
                            score_after=credit_score,
                        )
                    )
                    if installment.installment_number == loan.duration_months:
                        loan.status = "completed"
                        credit_score = self._clamp(credit_score + 3)
                        self.credit_history_repository.create(
                            CreditHistory(
                                user_id=user_id,
                                turn_number=turn_number,
                                delta=3,
                                reason="loan_complete",
                                score_after=credit_score,
                            )
                        )
                else:
                    installment.status = "overdue"
                    is_overdue = True
                    credit_score = self._clamp(credit_score - 4)
                    self.credit_history_repository.create(
                        CreditHistory(
                            user_id=user_id,
                            turn_number=turn_number,
                            delta=-4,
                            reason="overdue",
                            score_after=credit_score,
                        )
                    )
                self.loan_repository.save_repayment(loan, installment)

        credit_score_delta = credit_score - state.credit_score
        total_asset_after = cash_balance + self._stock_value_total(user_id)

        next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)

        turn = self.turn_repository.create(
            Turn(
                user_id=user_id,
                turn_number=turn_number,
                year=year,
                month=month,
                salary_received=salary_received,
                fixed_expense_total=fixed_expense_total,
                variable_expense_total=variable_expense_total,
                food_choice=choice.food_choice,
                shopping_choice=choice.shopping_choice,
                leisure_choice=choice.leisure_choice,
                consume_score_delta=consume_score_delta,
                credit_score_delta=credit_score_delta,
                loan_repayment_amount=loan_repayment_amount,
                is_overdue=is_overdue,
                cash_balance_after=cash_balance,
                total_asset_after=total_asset_after,
            )
        )

        state.current_turn = turn_number + 1
        state.current_year = next_year
        state.current_month = next_month
        state.cash_balance = cash_balance
        state.credit_score = credit_score
        state.consume_score = consume_score
        self.state_repository.save(state)

        return turn

    def _get_state(self, user_id: int) -> SimulationState:
        state = self.state_repository.find_by_user(user_id)
        if state is None:
            raise not_found("시뮬레이션 정보를 찾을 수 없습니다")
        return state

    def _stock_value_total(self, user_id: int) -> int:
        return sum(holding.current_value for holding in self.stock_repository.find_all_by_user(user_id))

    @staticmethod
    def _clamp(score: int) -> int:
        return max(0, min(100, score))
