"""턴 처리 API 핵심 로직 검증 (finance-simulater/backend#14)."""

from unittest.mock import MagicMock

import pytest

from app.api.v1.credit.model import CreditGradePolicy
from app.api.v1.fixed_expense.model import FixedExpense
from app.api.v1.loan.model import Loan, RepaymentSchedule
from app.api.v1.simulation.model import SimulationState
from app.api.v1.simulation.schema import TurnChoiceRequest
from app.api.v1.simulation.service import SimulationService
from app.api.v1.user.model import User
from app.core.exceptions import AppHTTPException


def make_state(**overrides) -> SimulationState:
    defaults = dict(
        user_id=1,
        current_turn=1,
        current_year=2026,
        current_month=1,
        cash_balance=1_000_000,
        credit_score=50,
        consume_score=50,
        status="active",
    )
    defaults.update(overrides)
    return SimulationState(**defaults)


def make_service(
    state: SimulationState,
    user: User,
    fixed_expenses: list[FixedExpense] | None = None,
    loan: Loan | None = None,
    installment: RepaymentSchedule | None = None,
) -> SimulationService:
    state.user = user

    state_repository = MagicMock()
    state_repository.find_by_user.return_value = state
    state_repository.save.side_effect = lambda s: s

    turn_repository = MagicMock()
    turn_repository.create.side_effect = lambda t: t

    fixed_expense_repository = MagicMock()
    fixed_expense_repository.find_all_by_user.return_value = fixed_expenses or []

    expense_repository = MagicMock()

    loan_repository = MagicMock()
    loan_repository.find_active_by_user.return_value = loan
    loan_repository.find_pending_installment.return_value = installment
    loan_repository.save_repayment.side_effect = lambda loan, installment: loan

    credit_repository = MagicMock()
    credit_repository.find_by_score.return_value = CreditGradePolicy(
        grade="B", grade_rank=6, min_score=65, max_score=74, credit_limit=3_000_000, base_interest_rate=5.5
    )

    credit_history_repository = MagicMock()

    stock_repository = MagicMock()
    stock_repository.find_all_by_user.return_value = []

    return SimulationService(
        db=MagicMock(),
        state_repository=state_repository,
        turn_repository=turn_repository,
        fixed_expense_repository=fixed_expense_repository,
        expense_repository=expense_repository,
        loan_repository=loan_repository,
        credit_repository=credit_repository,
        credit_history_repository=credit_history_repository,
        stock_repository=stock_repository,
    )


def test_advance_turn_without_loan_computes_expenses_and_consume_score() -> None:
    state = make_state()
    user = User(id=1, monthly_salary=2_000_000)
    fixed_expenses = [FixedExpense(name="월세", amount=500_000)]
    service = make_service(state, user, fixed_expenses=fixed_expenses)

    turn = service.advance_turn(
        1, TurnChoiceRequest(food_choice="normal", shopping_choice="save", leisure_choice="much")
    )

    # variable = 2,000,000 * (10 + 5 + 30) / 100 = 900,000
    assert turn.variable_expense_total == 900_000
    assert turn.fixed_expense_total == 500_000
    assert turn.salary_received == 2_000_000
    assert turn.cash_balance_after == 1_000_000 + 2_000_000 - 500_000 - 900_000
    # consume_score_delta = 0(normal) + 2(save) - 5(much) = -3
    assert turn.consume_score_delta == -3
    assert state.consume_score == 47
    assert state.current_turn == 2
    assert state.current_month == 2
    assert turn.is_overdue is False
    assert turn.loan_repayment_amount == 0


def test_advance_turn_records_clamped_consume_score_delta_at_upper_bound() -> None:
    # consume_score=99, raw delta 합산은 +6("save" 3개)이지만 100을 넘을 수 없으므로
    # 실제 반영된 변화량(+1)이 turn.consume_score_delta에 기록되어야 한다
    state = make_state(consume_score=99)
    user = User(id=1, monthly_salary=2_000_000)
    service = make_service(state, user)

    turn = service.advance_turn(
        1, TurnChoiceRequest(food_choice="save", shopping_choice="save", leisure_choice="save")
    )

    assert state.consume_score == 100
    assert turn.consume_score_delta == 1


def test_advance_turn_rolls_over_year_on_december() -> None:
    state = make_state(current_month=12)
    user = User(id=1, monthly_salary=1_000_000)
    service = make_service(state, user)

    service.advance_turn(1, TurnChoiceRequest(food_choice="normal", shopping_choice="normal", leisure_choice="normal"))

    assert state.current_month == 1
    assert state.current_year == 2027


def test_advance_turn_completes_simulation_on_final_turn() -> None:
    state = make_state(current_turn=24)
    user = User(id=1, monthly_salary=2_000_000)
    service = make_service(state, user)

    service.advance_turn(1, TurnChoiceRequest(food_choice="normal", shopping_choice="normal", leisure_choice="normal"))

    assert state.current_turn == 25
    assert state.status == "completed"


def test_advance_turn_defers_completion_while_active_loan_remains() -> None:
    state = make_state(current_turn=24)
    user = User(id=1, monthly_salary=2_000_000)
    loan = Loan(id=10, duration_months=12, remaining_balance=600_000, status="active")
    service = make_service(state, user, loan=loan, installment=None)

    service.advance_turn(1, TurnChoiceRequest(food_choice="normal", shopping_choice="normal", leisure_choice="normal"))

    assert state.current_turn == 25
    assert state.status == "active"


def test_advance_turn_completes_once_final_installment_paid_after_turn_limit() -> None:
    state = make_state(current_turn=24, cash_balance=1_000_000)
    user = User(id=1, monthly_salary=2_000_000)
    loan = Loan(id=10, duration_months=6, remaining_balance=100_000, status="active")
    installment = RepaymentSchedule(installment_number=6, amount=100_000, status="pending")
    service = make_service(state, user, loan=loan, installment=installment)

    service.advance_turn(1, TurnChoiceRequest(food_choice="normal", shopping_choice="normal", leisure_choice="normal"))

    assert loan.status == "completed"
    assert state.status == "completed"


def test_advance_turn_pays_installment_on_time_and_bumps_credit_score() -> None:
    state = make_state(cash_balance=1_000_000, credit_score=50)
    user = User(id=1, monthly_salary=2_000_000)
    loan = Loan(id=10, duration_months=6, remaining_balance=600_000, status="active")
    installment = RepaymentSchedule(installment_number=3, amount=100_000, status="pending")
    service = make_service(state, user, loan=loan, installment=installment)

    turn = service.advance_turn(
        1, TurnChoiceRequest(food_choice="normal", shopping_choice="normal", leisure_choice="normal")
    )

    assert installment.status == "paid"
    assert loan.remaining_balance == 500_000
    assert turn.loan_repayment_amount == 100_000
    assert turn.is_overdue is False
    assert turn.credit_score_delta == 1
    assert state.credit_score == 51


def test_advance_turn_last_installment_completes_loan_with_bonus() -> None:
    state = make_state(credit_score=50)
    user = User(id=1, monthly_salary=2_000_000)
    loan = Loan(id=10, duration_months=6, remaining_balance=100_000, status="active")
    installment = RepaymentSchedule(installment_number=6, amount=100_000, status="pending")
    service = make_service(state, user, loan=loan, installment=installment)

    turn = service.advance_turn(
        1, TurnChoiceRequest(food_choice="normal", shopping_choice="normal", leisure_choice="normal")
    )

    assert loan.status == "completed"
    # +1(정상납입) +3(완납보너스)
    assert turn.credit_score_delta == 4
    assert state.credit_score == 54


def test_advance_turn_overdue_when_balance_insufficient() -> None:
    state = make_state(cash_balance=50_000, credit_score=50)
    user = User(id=1, monthly_salary=0)
    loan = Loan(id=10, duration_months=6, remaining_balance=600_000, status="active")
    installment = RepaymentSchedule(installment_number=1, amount=100_000, status="pending")
    service = make_service(state, user, loan=loan, installment=installment)

    turn = service.advance_turn(
        1, TurnChoiceRequest(food_choice="save", shopping_choice="save", leisure_choice="save")
    )

    assert installment.status == "overdue"
    assert turn.is_overdue is True
    assert turn.loan_repayment_amount == 0
    assert turn.credit_score_delta == -4
    assert state.credit_score == 46


def test_advance_turn_rejects_when_expenses_exceed_balance() -> None:
    state = make_state(cash_balance=0, consume_score=50)
    user = User(id=1, monthly_salary=100_000)
    fixed_expenses = [FixedExpense(name="월세", amount=90_000)]
    service = make_service(state, user, fixed_expenses=fixed_expenses)

    with pytest.raises(AppHTTPException) as exc_info:
        service.advance_turn(
            1, TurnChoiceRequest(food_choice="much", shopping_choice="much", leisure_choice="much")
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "INSUFFICIENT_BALANCE"
    # 잔액 초과 시 상태/지출이 변경되지 않아야 함
    assert state.current_turn == 1
    assert state.consume_score == 50
    service.expense_repository.create_many.assert_not_called()
    service.turn_repository.create.assert_not_called()


def test_advance_turn_rejects_completed_simulation() -> None:
    state = make_state(status="completed")
    user = User(id=1, monthly_salary=2_000_000)
    service = make_service(state, user)

    with pytest.raises(AppHTTPException) as exc_info:
        service.advance_turn(
            1, TurnChoiceRequest(food_choice="normal", shopping_choice="normal", leisure_choice="normal")
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "SIMULATION_ALREADY_COMPLETED"


def test_get_turn_not_found_raises_turn_not_found_code() -> None:
    state = make_state()
    user = User(id=1, monthly_salary=2_000_000)
    service = make_service(state, user)
    service.turn_repository.find_by_user_and_turn.return_value = None

    with pytest.raises(AppHTTPException) as exc_info:
        service.get_turn(1, 99)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "TURN_NOT_FOUND"
