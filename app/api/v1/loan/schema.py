from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    applied_credit_grade: str
    applied_credit_score: int
    applied_limit: int
    interest_rate: Decimal
    principal: int
    duration_months: int
    monthly_payment: int
    total_repayment: int
    remaining_balance: int
    status: str
    started_turn: int
    created_at: datetime


class GradeOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grade: str
    credit_limit: int
    base_interest_rate: Decimal


class LoanEligibilityResponse(BaseModel):
    credit_grade: str
    credit_score: int
    credit_limit: int
    base_interest_rate: Decimal
    grade_comparison: list[GradeOption]


class LoanQuoteResponse(BaseModel):
    principal: int
    duration_months: int
    interest_rate: Decimal
    monthly_payment: int
    total_repayment: int
    total_interest: int


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
