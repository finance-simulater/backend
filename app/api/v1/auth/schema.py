from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.api.v1.user.schema import UserResponse


class SignupRequest(BaseModel):
    email: EmailStr
    email_verification_token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=50)
    profile_image_seed: str = Field(min_length=1, max_length=50)
    job_type: Literal["employee", "freelancer", "other"]
    monthly_salary: int = Field(ge=0)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class SignupResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class EmailVerificationRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class EmailVerificationSendRequest(BaseModel):
    email: EmailStr


class EmailVerificationResponse(BaseModel):
    email_verification_token: str
    expires_in: int


class MessageResponse(BaseModel):
    message: str
