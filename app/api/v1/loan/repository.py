from datetime import datetime

from app.api.v1.loan.model import Loan
from app.api.v1.loan.schema import LoanCreate


_LOANS = [
    Loan(
        id=1,
        user_id=1,
        applied_credit_grade="C",
        applied_credit_score=50,
        applied_limit=1_000_000,
        interest_rate=8.5,
        principal=500_000,
        duration_months=6,
        monthly_payment=85_000,
        total_repayment=510_000,
        remaining_balance=500_000,
        status="active",
        started_turn=1,
        created_at=datetime.now(),
    )
]


class LoanRepository:
    def find_all(self) -> list[Loan]:
        return _LOANS

    def find_by_id(self, loan_id: int) -> Loan | None:
        return next((loan for loan in _LOANS if loan.id == loan_id), None)

    def create(self, loan_create: LoanCreate) -> Loan:
        loan = Loan(id=len(_LOANS) + 1, status="active", created_at=datetime.now(), **loan_create.model_dump())
        _LOANS.append(loan)
        return loan
