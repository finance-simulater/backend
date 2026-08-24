from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

CreditHistoryReason = Literal["loan_payment", "overdue", "loan_complete", "loan_default"]


class CreditScoreResponse(BaseModel):
    score: int
    grade: str
    credit_limit: int
    next_grade: str | None = None
    score_to_next_grade: int | None = None


class CreditHistoryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    turn_number: int
    delta: int
    reason: CreditHistoryReason
    score_after: int
    created_at: datetime
