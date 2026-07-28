from sqlalchemy.orm import Session

from app.api.v1.credit.model import CreditGradePolicy, CreditHistory
from app.core.exceptions import not_found


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


def get_grade_policy_or_404(repository: CreditGradePolicyRepository, credit_score: int) -> CreditGradePolicy:
    grade_policy = repository.find_by_score(credit_score)
    if grade_policy is None:
        raise not_found("신용 등급 정보를 찾을 수 없습니다")
    return grade_policy


class CreditHistoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, credit_history: CreditHistory) -> CreditHistory:
        self.db.add(credit_history)
        self.db.commit()
        self.db.refresh(credit_history)
        return credit_history
