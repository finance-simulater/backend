from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field
from pydantic import ConfigDict


class UserCreate(BaseModel):
    email: EmailStr
    password: str | None = Field(default=None, max_length=255)
    nickname: str = Field(min_length=1, max_length=50)
    profile_image_seed: str = Field(min_length=1, max_length=50)
    job_type: Literal["employee", "freelancer", "other"]
    monthly_salary: int = Field(ge=0)
    provider: Literal["local", "kakao", "google"] = "local"
    social_id: str | None = Field(default=None, max_length=255)


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
    created_at: datetime
    updated_at: datetime
