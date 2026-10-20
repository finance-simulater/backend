from typing import Literal

from pydantic import BaseModel, EmailStr, Field
from pydantic import ConfigDict

from app.core.types import MAX_MONTHLY_AMOUNT, UtcDatetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str | None = Field(default=None, min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=50)
    profile_image_seed: str = Field(min_length=1, max_length=50)
    job_type: Literal["employee", "freelancer", "other"]
    monthly_salary: int = Field(ge=0)
    provider: Literal["local", "kakao", "google"] = "local"
    social_id: str | None = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    monthly_salary: int = Field(ge=0, le=MAX_MONTHLY_AMOUNT)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nickname: str
    profile_image_seed: str
    job_type: str
    monthly_salary: int
    is_email_verified: bool
    provider: str
    social_id: str | None = None
    onboarding_step: int
    created_at: UtcDatetime
    updated_at: UtcDatetime
