from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.types import MAX_MONTHLY_AMOUNT, UtcDatetime


class FixedExpenseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    amount: int = Field(ge=1, le=MAX_MONTHLY_AMOUNT)


class FixedExpenseUpdate(BaseModel):
    """보낸 필드만 수정한다. 미전송 필드는 변경하지 않고, 명시적 null은 422로 거절한다 (spec#19).

    `str | None`은 "미전송"을 기본값 None으로 표현하기 위한 것이다. 기본값에는 validator가 돌지 않으므로
    아래 validator는 클라이언트가 실제로 null을 보낸 경우에만 실행된다.
    """

    name: str | None = Field(default=None, min_length=1, max_length=50)
    amount: int | None = Field(default=None, ge=1, le=MAX_MONTHLY_AMOUNT)

    @field_validator("name", "amount", mode="before")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            # 입력값을 메시지에 넣지 않는다 (CONVENTIONS — validator 메시지 규칙)
            raise ValueError("null은 허용되지 않습니다. 변경하지 않을 필드는 보내지 마세요")
        return value


class FixedExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    amount: int
    created_at: UtcDatetime
    updated_at: UtcDatetime
