"""LoanRepository 통합 테스트"""

import pytest

from app.api.v1.loan.model import Loan, RepaymentSchedule
from app.api.v1.loan.repository import LoanRepository
from tests.integration.factories import make_user

pytestmark = pytest.mark.integration


def make_loan(user_id: int, grade: str, **overrides) -> Loan:
    defaults = dict(
        user_id=user_id,
        applied_credit_grade=grade,
        applied_credit_score=70,
        applied_limit=3_000_000,
        interest_rate="5.50",
        principal=1_000_000,
        duration_months=3,
        monthly_payment=340_000,
        total_repayment=1_020_000,
        remaining_balance=1_000_000,
        started_turn=1,
    )
    defaults.update(overrides)
    return Loan(**defaults)


def make_schedule(**overrides) -> RepaymentSchedule:
    defaults = dict(installment_number=1, due_turn=2, amount=340_000)
    defaults.update(overrides)
    return RepaymentSchedule(**defaults)


def test_create_with_schedule_persists_loan_and_installments(db_session):
    user = make_user(db_session)
    repository = LoanRepository(db_session)

    loan = repository.create_with_schedule(
        make_loan(user.id, "B"),
        [make_schedule(installment_number=1, due_turn=2), make_schedule(installment_number=2, due_turn=3)],
    )

    assert loan.id is not None
    schedule = repository.find_schedule_by_loan(loan.id)
    assert [s.installment_number for s in schedule] == [1, 2]


def test_find_active_by_user_only_returns_active_loan(db_session):
    user = make_user(db_session)
    repository = LoanRepository(db_session)
    active = repository.create_with_schedule(make_loan(user.id, "B"), [make_schedule()])

    found = repository.find_active_by_user(user.id)

    assert found.id == active.id


def test_find_active_by_user_returns_none_after_completion(db_session):
    user = make_user(db_session)
    repository = LoanRepository(db_session)
    loan = repository.create_with_schedule(make_loan(user.id, "B"), [make_schedule()])

    loan.status = "completed"
    db_session.flush()

    assert repository.find_active_by_user(user.id) is None


def test_find_due_installments_filters_pending_and_overdue_up_to_turn(db_session):
    user = make_user(db_session)
    repository = LoanRepository(db_session)
    loan = repository.create_with_schedule(
        make_loan(user.id, "B"),
        [
            make_schedule(installment_number=1, due_turn=1, status="paid"),
            make_schedule(installment_number=2, due_turn=2, status="pending"),
            make_schedule(installment_number=3, due_turn=3, status="pending"),
        ],
    )

    due = repository.find_due_installments(loan.id, up_to_turn=2)

    assert [s.installment_number for s in due] == [2]


def test_save_repayment_updates_loan_and_installments(db_session):
    user = make_user(db_session)
    repository = LoanRepository(db_session)
    loan = repository.create_with_schedule(
        make_loan(user.id, "B"),
        [make_schedule(installment_number=1, due_turn=2, status="pending")],
    )
    schedule = repository.find_schedule_by_loan(loan.id)
    schedule[0].status = "paid"
    loan.remaining_balance = 0
    loan.status = "completed"

    repository.save_repayment(loan, schedule)

    reloaded = repository.find_by_id(loan.id)
    assert reloaded.status == "completed"
    assert repository.find_schedule_by_loan(loan.id)[0].status == "paid"
