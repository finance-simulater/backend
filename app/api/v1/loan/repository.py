from app.api.v1.loan.model import Loan
from app.api.v1.loan.schema import LoanCreate


_LOANS = [
    Loan(id=1, user_id=1, amount=10_000_000, status="active"),
    Loan(id=2, user_id=2, amount=5_000_000, status="pending"),
]


class LoanRepository:
    def find_all(self) -> list[Loan]:
        return _LOANS

    def find_by_id(self, loan_id: int) -> Loan | None:
        return next((loan for loan in _LOANS if loan.id == loan_id), None)

    def create(self, loan_create: LoanCreate) -> Loan:
        loan = Loan(
            id=len(_LOANS) + 1,
            user_id=loan_create.user_id,
            amount=loan_create.amount,
            status=loan_create.status,
        )
        _LOANS.append(loan)
        return loan
