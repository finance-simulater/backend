from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import DecimalNumber, UtcDatetime


class LoanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    applied_credit_grade: str
    applied_credit_score: int
    applied_limit: int
    interest_rate: DecimalNumber
    principal: int
    duration_months: int
    monthly_payment: int
    total_repayment: int
    remaining_balance: int
    status: str
    started_turn: int
    created_at: UtcDatetime


class GradeOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grade: str
    credit_limit: int
    base_interest_rate: DecimalNumber


class LoanEligibilityResponse(BaseModel):
    credit_grade: str
    credit_score: int
    credit_limit: int
    base_interest_rate: DecimalNumber
    grade_comparison: list[GradeOption]


class LoanQuoteResponse(BaseModel):
    principal: int
    duration_months: int
    interest_rate: DecimalNumber
    monthly_payment: int
    total_repayment: int
    total_interest: int


class LoanDuration(IntEnum):
    """대출 기간(개월). 쿼리 파라미터용.

    쿼리 값은 문자열("12")로 들어오는데 Pydantic v2의 Literal[3, 6, 12]는 문자열을 정수로
    바꾸지 않아 항상 422가 난다(#67). IntEnum은 "12" → 12로 변환해 검증한다.
    """

    THREE = 3
    SIX = 6
    TWELVE = 12


class LoanApplicationRequest(BaseModel):
    principal: int = Field(gt=0)
    duration_months: Literal[3, 6, 12]


class RepaymentScheduleItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    installment_number: int
    due_turn: int
    amount: int
    status: str
    paid_at_turn: int | None = None


class LoanStatusResponse(LoanResponse):
    next_due_turn: int | None
    remaining_installments: int
    schedule: list[RepaymentScheduleItem]
