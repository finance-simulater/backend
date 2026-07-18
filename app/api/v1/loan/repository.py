from sqlalchemy.orm import Session

from app.api.v1.loan.model import Loan, RepaymentSchedule


class LoanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_all(self) -> list[Loan]:
        return self.db.query(Loan).order_by(Loan.id).all()

    def find_by_id(self, loan_id: int) -> Loan | None:
        return self.db.query(Loan).filter(Loan.id == loan_id).first()

    def find_active_by_user(self, user_id: int) -> Loan | None:
        return (
            self.db.query(Loan)
            .filter(Loan.user_id == user_id, Loan.status == "active")
            .first()
        )

    def find_schedule_by_loan(self, loan_id: int) -> list[RepaymentSchedule]:
        return (
            self.db.query(RepaymentSchedule)
            .filter(RepaymentSchedule.loan_id == loan_id)
            .order_by(RepaymentSchedule.installment_number)
            .all()
        )

    def create_with_schedule(self, loan: Loan, schedule: list[RepaymentSchedule]) -> Loan:
        self.db.add(loan)
        self.db.flush()
        for installment in schedule:
            installment.loan_id = loan.id
        self.db.add_all(schedule)
        self.db.commit()
        self.db.refresh(loan)
        return loan
