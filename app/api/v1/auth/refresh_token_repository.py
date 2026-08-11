from redis import Redis
from redis.exceptions import RedisError

from app.core.security import hash_token


class RefreshTokenStoreError(RuntimeError):
    pass


class RefreshTokenRepository:
    key_prefix = "auth:refresh:"

    def __init__(self, client: Redis) -> None:
        self.client = client

    def save(self, token: str, user_id: int, expires_in_seconds: int) -> None:
        try:
            self.client.set(
                self._key(token),
                str(user_id),
                ex=expires_in_seconds,
            )
        except RedisError as exc:
            raise RefreshTokenStoreError("Failed to save refresh token") from exc

    def consume(self, token: str) -> int | None:
        try:
            user_id = self.client.getdel(self._key(token))
        except RedisError as exc:
            raise RefreshTokenStoreError("Failed to consume refresh token") from exc
        return int(user_id) if user_id is not None else None

    def delete(self, token: str) -> None:
        try:
            self.client.delete(self._key(token))
        except RedisError as exc:
            raise RefreshTokenStoreError("Failed to delete refresh token") from exc

    def _key(self, token: str) -> str:
        return f"{self.key_prefix}{hash_token(token)}"
