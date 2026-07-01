from sqlalchemy.orm import Session

from app.api.v1.loan.model import Loan
from app.api.v1.loan.schema import LoanCreate


class LoanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_all(self) -> list[Loan]:
        return self.db.query(Loan).order_by(Loan.id).all()

    def find_by_id(self, loan_id: int) -> Loan | None:
        return self.db.query(Loan).filter(Loan.id == loan_id).first()

    def create(self, loan_create: LoanCreate) -> Loan:
        loan = Loan(**loan_create.model_dump())
        self.db.add(loan)
        self.db.commit()
        self.db.refresh(loan)
        return loan
