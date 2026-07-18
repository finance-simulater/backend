from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.api.v1.credit.model import CreditGradePolicy
from app.api.v1.credit.repository import CreditGradePolicyRepository
from app.api.v1.loan.model import Loan, RepaymentSchedule
from app.api.v1.loan.repository import LoanRepository
from app.api.v1.loan.schema import (
    GradeOption,
    LoanEligibilityResponse,
    LoanQuoteResponse,
    LoanResponse,
    LoanStatusResponse,
    RepaymentScheduleItem,
)
from app.api.v1.simulation.model import SimulationState
from app.api.v1.simulation.repository import SimulationStateRepository
from app.core.exceptions import conflict, not_found, unprocessable

# 등급별 기본금리에서 대출 기간에 따라 +-2%p 가산/차감 (3개월 -2, 6개월 0, 12개월 +2)
DURATION_RATE_ADJUSTMENT: dict[int, Decimal] = {
    3: Decimal("-2.0"),
    6: Decimal("0.0"),
    12: Decimal("2.0"),
}


class LoanService:
    def __init__(
        self,
        db: Session,
        repository: LoanRepository | None = None,
        credit_repository: CreditGradePolicyRepository | None = None,
        simulation_repository: SimulationStateRepository | None = None,
    ) -> None:
        self.repository = repository or LoanRepository(db)
        self.credit_repository = credit_repository or CreditGradePolicyRepository(db)
        self.simulation_repository = simulation_repository or SimulationStateRepository(db)

    def get_loans(self) -> list[Loan]:
        return self.repository.find_all()

    def get_loan(self, loan_id: int) -> Loan:
        loan = self.repository.find_by_id(loan_id)
        if loan is None:
            raise not_found("대출 정보를 찾을 수 없습니다")
        return loan

    def get_schedule(self, loan_id: int) -> list[RepaymentSchedule]:
        self.get_loan(loan_id)
        return self.repository.find_schedule_by_loan(loan_id)

    def get_eligibility(self, user_id: int) -> LoanEligibilityResponse:
        simulation_state = self._get_simulation_state(user_id)
        grade_policy = self._get_grade_policy(simulation_state.credit_score)
        comparison = self.credit_repository.find_all_ordered()
        return LoanEligibilityResponse(
            credit_grade=grade_policy.grade,
            credit_score=simulation_state.credit_score,
            credit_limit=grade_policy.credit_limit,
            base_interest_rate=grade_policy.base_interest_rate,
            grade_comparison=[GradeOption.model_validate(g) for g in comparison],
        )

    def get_quote(self, user_id: int, principal: int, duration_months: int) -> LoanQuoteResponse:
        simulation_state = self._get_simulation_state(user_id)
        grade_policy = self._get_grade_policy(simulation_state.credit_score)
        interest_rate = self._resolve_interest_rate(grade_policy.base_interest_rate, duration_months)
        monthly_payment = self._calculate_monthly_payment(principal, interest_rate, duration_months)
        total_repayment = monthly_payment * duration_months
        return LoanQuoteResponse(
            principal=principal,
            duration_months=duration_months,
            interest_rate=interest_rate,
            monthly_payment=monthly_payment,
            total_repayment=total_repayment,
            total_interest=total_repayment - principal,
        )

    def get_active_loan_status(self, user_id: int) -> LoanStatusResponse:
        loan = self.repository.find_active_by_user(user_id)
        if loan is None:
            raise not_found("진행 중인 대출이 없습니다")
        schedule = self.repository.find_schedule_by_loan(loan.id)
        pending = [item for item in schedule if item.status == "pending"]
        return LoanStatusResponse(
            **LoanResponse.model_validate(loan).model_dump(),
            next_due_turn=pending[0].due_turn if pending else None,
            remaining_installments=len(pending),
            schedule=[RepaymentScheduleItem.model_validate(item) for item in schedule],
        )

    def apply_for_loan(self, user_id: int, principal: int, duration_months: int) -> Loan:
        if self.repository.find_active_by_user(user_id) is not None:
            raise conflict("이미 진행 중인 대출이 있어 신규 신청이 불가합니다")

        simulation_state = self._get_simulation_state(user_id)
        grade_policy = self._get_grade_policy(simulation_state.credit_score)

        # AI 자동심사->신용등급별 한도 초과 여부 승인/거절 판단
        if principal > grade_policy.credit_limit:
            raise unprocessable(
                f"신청 금액이 {grade_policy.grade}등급 한도({grade_policy.credit_limit:,}원)를 초과했습니다"
            )

        interest_rate = self._resolve_interest_rate(grade_policy.base_interest_rate, duration_months)
        monthly_payment = self._calculate_monthly_payment(principal, interest_rate, duration_months)
        total_repayment = monthly_payment * duration_months
        started_turn = simulation_state.current_turn

        loan = Loan(
            user_id=user_id,
            applied_credit_grade=grade_policy.grade,
            applied_credit_score=simulation_state.credit_score,
            applied_limit=grade_policy.credit_limit,
            interest_rate=interest_rate,
            principal=principal,
            duration_months=duration_months,
            monthly_payment=monthly_payment,
            total_repayment=total_repayment,
            remaining_balance=total_repayment,
            started_turn=started_turn,
        )
        schedule = [
            RepaymentSchedule(
                installment_number=installment_number,
                due_turn=started_turn + installment_number,
                amount=monthly_payment,
            )
            for installment_number in range(1, duration_months + 1)
        ]
        return self.repository.create_with_schedule(loan, schedule)

    def _get_simulation_state(self, user_id: int) -> SimulationState:
        simulation_state = self.simulation_repository.find_by_user(user_id)
        if simulation_state is None:
            raise not_found("시뮬레이션 정보를 찾을 수 없습니다")
        return simulation_state

    def _get_grade_policy(self, credit_score: int) -> CreditGradePolicy:
        grade_policy = self.credit_repository.find_by_score(credit_score)
        if grade_policy is None:
            raise not_found("신용 등급 정보를 찾을 수 없습니다")
        return grade_policy

    @staticmethod
    def _resolve_interest_rate(base_rate: Decimal, duration_months: int) -> Decimal:
        rate = base_rate + DURATION_RATE_ADJUSTMENT[duration_months]
        return max(rate, Decimal("0.0"))

    @staticmethod
    def _calculate_monthly_payment(principal: int, annual_rate: Decimal, duration_months: int) -> int:
        # 원리금 균등상환 (equal installment / amortized loan) 공식
        monthly_rate = annual_rate / Decimal(100) / Decimal(12)
        if monthly_rate == 0:
            raw_payment = Decimal(principal) / Decimal(duration_months)
        else:
            growth_factor = (1 + monthly_rate) ** duration_months
            raw_payment = Decimal(principal) * monthly_rate * growth_factor / (growth_factor - 1)
        return int(raw_payment.to_integral_value(rounding=ROUND_HALF_UP))
