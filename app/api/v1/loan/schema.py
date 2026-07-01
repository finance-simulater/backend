from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoanCreate(BaseModel):
    user_id: int = Field(gt=0)
    applied_credit_grade: str = Field(min_length=1, max_length=2)
    applied_credit_score: int = Field(ge=0, le=100)
    applied_limit: int = Field(ge=0)
    interest_rate: Decimal = Field(ge=0)
    principal: int = Field(gt=0)
    duration_months: Literal[3, 6, 12]
    monthly_payment: int = Field(gt=0)
    total_repayment: int = Field(gt=0)
    remaining_balance: int = Field(ge=0)
    started_turn: int = Field(gt=0)


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
