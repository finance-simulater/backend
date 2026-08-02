from datetime import date

from sqlalchemy.orm import Session

from app.api.v1.credit.model import CreditHistory
from app.api.v1.credit.repository import (
    CreditGradePolicyRepository,
    CreditHistoryRepository,
    get_grade_policy_or_404,
)
from app.api.v1.credit.schema import CreditHistoryReason
from app.api.v1.expense.model import Expense
from app.api.v1.expense.repository import ExpenseRepository
from app.api.v1.fixed_expense.repository import FixedExpenseRepository
from app.api.v1.loan.repository import LoanRepository
from app.api.v1.simulation.model import SimulationState, Turn
from app.api.v1.simulation.repository import (
    SimulationStateRepository,
    TurnRepository,
    get_simulation_state_or_404,
)
from app.api.v1.simulation.schema import ConsumeLevel, SimulationStateResponse, TurnChoiceRequest
from app.api.v1.stock.repository import StockHoldingRepository
from app.core.exceptions import conflict, not_found, unprocessable
from app.core.scoring import clamp_score

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

# 시뮬레이션 총 진행 턴 수 (1턴 = 1개월, 24턴 = 2년) — 이 턴까지 처리하면 시뮬레이션 종료
TOTAL_TURNS = 24

# 연체가 이 횟수(3개월) 연속되면 원금 상환 실패로 간주해 대출을 부도 처리한다 (실제 3개월 연체 시 채무불이행자 등록 관행과 동일)
MAX_CONSECUTIVE_OVERDUE = 3

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
        fixed_expense_repository: FixedExpenseRepository | None = None,
        expense_repository: ExpenseRepository | None = None,
        loan_repository: LoanRepository | None = None,
        credit_repository: CreditGradePolicyRepository | None = None,
        credit_history_repository: CreditHistoryRepository | None = None,
        stock_repository: StockHoldingRepository | None = None,
    ) -> None:
        self.db = db
        self.state_repository = state_repository or SimulationStateRepository(db)
        self.turn_repository = turn_repository or TurnRepository(db)
        self.fixed_expense_repository = fixed_expense_repository or FixedExpenseRepository(db)
        self.expense_repository = expense_repository or ExpenseRepository(db)
        self.loan_repository = loan_repository or LoanRepository(db)
        self.credit_repository = credit_repository or CreditGradePolicyRepository(db)
        self.credit_history_repository = credit_history_repository or CreditHistoryRepository(db)
        self.stock_repository = stock_repository or StockHoldingRepository(db)

    def get_state(self, user_id: int) -> SimulationStateResponse:
        state = get_simulation_state_or_404(self.state_repository, user_id)
        stock_value_total = self.stock_repository.sum_current_value_by_user(user_id)
        total_asset = state.cash_balance + stock_value_total
        grade_policy = get_grade_policy_or_404(self.credit_repository, state.credit_score)
        return SimulationStateResponse(
            current_turn=state.current_turn,
            current_year=state.current_year,
            current_month=state.current_month,
            cash_balance=state.cash_balance,
            total_asset=total_asset,
            stock_ratio=(stock_value_total / total_asset) if total_asset else 0.0,
            credit_score=state.credit_score,
            credit_grade=grade_policy.grade,
            consume_score=state.consume_score,
            has_active_loan=self.loan_repository.find_active_by_user(user_id) is not None,
            status=state.status,
        )

    def list_turns(self, user_id: int, cursor: int | None, size: int) -> list[Turn]:
        get_simulation_state_or_404(self.state_repository, user_id)
        return self.turn_repository.find_by_user_paginated(user_id, cursor, size)

    def get_turn(self, user_id: int, turn_number: int) -> Turn:
        get_simulation_state_or_404(self.state_repository, user_id)
        turn = self.turn_repository.find_by_user_and_turn(user_id, turn_number)
        if turn is None:
            raise not_found("해당 턴을 찾을 수 없습니다", code="TURN_NOT_FOUND")
        return turn

    def advance_turn(self, user_id: int, choice: TurnChoiceRequest) -> Turn:
        # user_id 행을 잠그고 시작해 동시 요청으로 인한 lost-update(급여 이중 지급 등)를 방지.
        # with_user=True로 users 테이블을 조인해 함께 가져와 별도 조회를 없앤다.
        state = get_simulation_state_or_404(self.state_repository, user_id, for_update=True, with_user=True)
        try:
            turn = self._advance_turn_locked(state, user_id, choice)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return turn

    def _advance_turn_locked(self, state: SimulationState, user_id: int, choice: TurnChoiceRequest) -> Turn:
        if state.status != "active":
            raise conflict("이미 완료된 시뮬레이션입니다", code="SIMULATION_ALREADY_COMPLETED")

        user = state.user

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
        cash_balance = state.cash_balance + salary_received - fixed_expense_total - variable_expense_total
        if cash_balance < 0:
            raise unprocessable(
                "이번 달 지출이 소득과 잔액을 초과합니다. 소비 수준을 낮춰 다시 시도해주세요",
                code="INSUFFICIENT_BALANCE",
            )

        if new_expenses:
            self.expense_repository.create_many(new_expenses)

        consume_score = clamp_score(state.consume_score + consume_score_delta)

        loan_repayment_amount = 0
        is_overdue = False
        credit_score = state.credit_score
        loan = self.loan_repository.find_active_by_user(user_id)
        if loan is not None:
            # 신규 도래분 + 이전에 연체된 회차를 함께 걷는다(실제 대출처럼 연체분이 누적됨)
            due_installments = self.loan_repository.find_due_installments(loan.id, turn_number)
            if due_installments:
                total_due = sum(i.amount for i in due_installments)
                if cash_balance >= total_due:
                    cash_balance -= total_due
                    loan_repayment_amount = total_due
                    for installment in due_installments:
                        installment.status = "paid"
                        installment.paid_at_turn = turn_number
                    loan.remaining_balance -= total_due

                    credit_score = clamp_score(credit_score + 1)
                    self._record_credit_history(user_id, turn_number, 1, "loan_payment", credit_score)

                    if due_installments[-1].installment_number == loan.duration_months:
                        loan.status = "completed"
                        credit_score = clamp_score(credit_score + 3)
                        self._record_credit_history(user_id, turn_number, 3, "loan_complete", credit_score)
                else:
                    for installment in due_installments:
                        installment.status = "overdue"
                    is_overdue = True
                    if len(due_installments) >= MAX_CONSECUTIVE_OVERDUE:
                        loan.status = "defaulted"
                        credit_score = clamp_score(credit_score - 10)
                        self._record_credit_history(user_id, turn_number, -10, "loan_default", credit_score)
                    else:
                        credit_score = clamp_score(credit_score - 4)
                        self._record_credit_history(user_id, turn_number, -4, "overdue", credit_score)
                self.loan_repository.save_repayment(loan, due_installments)

        consume_score_delta = consume_score - state.consume_score
        credit_score_delta = credit_score - state.credit_score
        total_asset_after = cash_balance + self.stock_repository.sum_current_value_by_user(user_id)

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
        # 활성 대출이 남아있으면 24턴이 지나도 완납할 때까지 종료를 보류한다
        has_active_loan = loan is not None and loan.status == "active"
        if turn_number >= TOTAL_TURNS and not has_active_loan:
            state.status = "completed"
        self.state_repository.save(state)

        return turn

    def _record_credit_history(
        self, user_id: int, turn_number: int, delta: int, reason: CreditHistoryReason, score_after: int
    ) -> None:
        self.credit_history_repository.create(
            CreditHistory(
                user_id=user_id,
                turn_number=turn_number,
                delta=delta,
                reason=reason,
                score_after=score_after,
            )
        )
