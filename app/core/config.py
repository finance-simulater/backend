from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "finance-simulater"
    database_url: str
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "change-me"
    debug: bool = False
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
