from sqlalchemy.orm import Session

from app.api.v1.credit.model import CreditGradePolicy


class CreditGradePolicyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_score(self, score: int) -> CreditGradePolicy | None:
        return (
            self.db.query(CreditGradePolicy)
            .filter(CreditGradePolicy.min_score <= score, CreditGradePolicy.max_score >= score)
            .first()
        )

    def find_all_ordered(self) -> list[CreditGradePolicy]:
        return self.db.query(CreditGradePolicy).order_by(CreditGradePolicy.grade_rank).all()
