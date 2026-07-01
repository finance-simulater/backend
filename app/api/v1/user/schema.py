from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    age: int | None = Field(default=None, ge=0)


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    age: int | None = None
