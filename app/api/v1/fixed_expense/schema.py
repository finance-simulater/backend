from pydantic import BaseModel, ConfigDict, Field

from app.core.types import UtcDatetime


class FixedExpenseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    amount: int = Field(ge=1)


class FixedExpenseUpdate(BaseModel):
    """보낸 필드만 수정한다. null·미전송 필드는 변경하지 않는다."""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    amount: int | None = Field(default=None, ge=1)


class FixedExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    amount: int
    created_at: UtcDatetime
    updated_at: UtcDatetime
