from sqlalchemy.orm import Session

from app.api.v1.credit.model import CreditHistory
from app.api.v1.credit.repository import (
    CreditGradePolicyRepository,
    CreditHistoryRepository,
    get_grade_policy_or_404,
)
from app.api.v1.credit.schema import CreditScoreResponse
from app.api.v1.simulation.repository import SimulationStateRepository, get_simulation_state_or_404


class CreditService:
    def __init__(
        self,
        db: Session,
        grade_repository: CreditGradePolicyRepository | None = None,
        history_repository: CreditHistoryRepository | None = None,
        simulation_repository: SimulationStateRepository | None = None,
    ) -> None:
        self.grade_repository = grade_repository or CreditGradePolicyRepository(db)
        self.history_repository = history_repository or CreditHistoryRepository(db)
        self.simulation_repository = simulation_repository or SimulationStateRepository(db)

    def get_score(self, user_id: int) -> CreditScoreResponse:
        simulation_state = get_simulation_state_or_404(self.simulation_repository, user_id)
        grade_policy = get_grade_policy_or_404(self.grade_repository, simulation_state.credit_score)

        # grade_rank가 1(A+)에 가까울수록 좋은 등급 — rank가 현재보다 낮은 등급 중 가장 가까운(rank가 가장 큰) 것이 다음 목표 등급.
        # grade_rank - 1을 직접 조회하지 않는 이유: 향후 등급이 추가/삭제돼 rank에 공백이 생겨도 안전하게 동작하도록 하기 위함.
        better_grades = [g for g in self.grade_repository.find_all_ordered() if g.grade_rank < grade_policy.grade_rank]
        next_grade_policy = max(better_grades, key=lambda g: g.grade_rank, default=None)

        return CreditScoreResponse(
            score=simulation_state.credit_score,
            grade=grade_policy.grade,
            credit_limit=grade_policy.credit_limit,
            next_grade=next_grade_policy.grade if next_grade_policy else None,
            score_to_next_grade=(
                next_grade_policy.min_score - simulation_state.credit_score if next_grade_policy else None
            ),
        )

    def get_history(self, user_id: int, cursor: int | None, size: int) -> list[CreditHistory]:
        get_simulation_state_or_404(self.simulation_repository, user_id)
        return self.history_repository.find_by_user_paginated(user_id, cursor, size)
