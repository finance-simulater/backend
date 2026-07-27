from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ConsumeLevel = Literal["save", "normal", "some", "much"]


class SimulationStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_turn: int
    current_year: int
    current_month: int
    cash_balance: int
    total_asset: int
    stock_ratio: float
    credit_score: int
    credit_grade: str | None
    consume_score: int
    has_active_loan: bool
    status: Literal["active", "completed"]


class TurnChoiceRequest(BaseModel):
    food_choice: ConsumeLevel
    shopping_choice: ConsumeLevel
    leisure_choice: ConsumeLevel


class TurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    turn_number: int
    year: int
    month: int
    salary_received: int
    fixed_expense_total: int
    variable_expense_total: int
    food_choice: ConsumeLevel
    shopping_choice: ConsumeLevel
    leisure_choice: ConsumeLevel
    consume_score_delta: int
    credit_score_delta: int
    loan_repayment_amount: int
    is_overdue: bool
    cash_balance_after: int
    total_asset_after: int
    created_at: datetime
