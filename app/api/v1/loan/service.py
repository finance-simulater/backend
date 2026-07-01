from sqlalchemy.orm import Session

from app.api.v1.loan.model import Loan
from app.api.v1.loan.repository import LoanRepository
from app.api.v1.loan.schema import LoanCreate
from app.core.exceptions import not_found


class LoanService:
    def __init__(self, db: Session, repository: LoanRepository | None = None) -> None:
        self.repository = repository or LoanRepository(db)

    def get_loans(self) -> list[Loan]:
        return self.repository.find_all()

    def get_loan(self, loan_id: int) -> Loan:
        loan = self.repository.find_by_id(loan_id)
        if loan is None:
            raise not_found("Loan not found")
        return loan

    def create_loan(self, loan_create: LoanCreate) -> Loan:
        return self.repository.create(loan_create)
