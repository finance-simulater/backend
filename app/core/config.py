from typing import Literal

from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "finance-simulater"
    database_url: str
    redis_url: str = "redis://localhost:6379"
    secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    refresh_cookie_name: str = "refresh_token"
    cookie_secure: bool = True
    email_provider: Literal["console", "ses"] = "console"
    email_from_address: EmailStr = "no-reply@fsimulation.store"
    email_verification_ttl_minutes: int = Field(default=10, ge=1, le=60)
    email_verification_ticket_ttl_minutes: int = Field(default=30, ge=1, le=120)
    email_resend_cooldown_seconds: int = Field(default=60, ge=1, le=3600)
    email_verification_max_attempts: int = Field(default=5, ge=1, le=10)
    debug: bool = False
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    aws_region: str = "ap-northeast-2"
    upload_bucket_name: str | None = None

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
