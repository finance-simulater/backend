from pydantic import BaseModel, Field


class LoanCreate(BaseModel):
    user_id: int = Field(gt=0)
    amount: int = Field(gt=0)
    status: str = Field(default="pending", min_length=1, max_length=30)


class LoanResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    status: str
