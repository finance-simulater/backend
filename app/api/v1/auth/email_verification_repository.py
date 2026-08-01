from dataclasses import dataclass

from redis import Redis
from redis.exceptions import RedisError

from app.core.security import hash_token


class VerificationStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailVerificationRecord:
    code_hash: str
    attempts: int


class EmailVerificationRepository:
    key_prefix = "auth:email-verification:"
    cooldown_key_prefix = "auth:email-verification-cooldown:"
    ticket_key_prefix = "auth:email-verification-ticket:"

    def __init__(self, client: Redis) -> None:
        self.client = client

    def reserve_send(self, email: str, cooldown_seconds: int) -> bool:
        try:
            return bool(
                self.client.set(
                    self._cooldown_key(email),
                    "1",
                    ex=cooldown_seconds,
                    nx=True,
                )
            )
        except RedisError as exc:
            raise VerificationStoreError("Failed to reserve email send") from exc

    def save(
        self,
        email: str,
        code_hash: str,
        expires_in_seconds: int,
    ) -> None:
        try:
            key = self._key(email)
            with self.client.pipeline() as pipeline:
                pipeline.hset(
                    key,
                    mapping={
                        "code_hash": code_hash,
                        "attempts": "0",
                    },
                )
                pipeline.expire(key, expires_in_seconds)
                pipeline.execute()
        except RedisError as exc:
            raise VerificationStoreError("Failed to save email verification") from exc

    def find(self, email: str) -> EmailVerificationRecord | None:
        try:
            values = self.client.hgetall(self._key(email))
        except RedisError as exc:
            raise VerificationStoreError("Failed to load email verification") from exc

        if not values:
            return None
        try:
            return EmailVerificationRecord(
                code_hash=values["code_hash"],
                attempts=int(values["attempts"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise VerificationStoreError("Invalid email verification data") from exc

    def increment_attempts(self, email: str) -> int:
        try:
            return int(self.client.hincrby(self._key(email), "attempts", 1))
        except RedisError as exc:
            raise VerificationStoreError(
                "Failed to update verification attempts"
            ) from exc

    def delete(self, email: str, include_cooldown: bool = False) -> None:
        keys = [self._key(email)]
        if include_cooldown:
            keys.append(self._cooldown_key(email))
        try:
            self.client.delete(*keys)
        except RedisError as exc:
            raise VerificationStoreError("Failed to delete email verification") from exc

    def save_ticket(
        self,
        token: str,
        email: str,
        expires_in_seconds: int,
    ) -> None:
        try:
            self.client.set(
                self._ticket_key(token),
                email.lower(),
                ex=expires_in_seconds,
            )
        except RedisError as exc:
            raise VerificationStoreError("Failed to save verification ticket") from exc

    def find_ticket_email(self, token: str) -> str | None:
        try:
            return self.client.get(self._ticket_key(token))
        except RedisError as exc:
            raise VerificationStoreError("Failed to load verification ticket") from exc

    def delete_ticket(self, token: str) -> None:
        try:
            self.client.delete(self._ticket_key(token))
        except RedisError as exc:
            raise VerificationStoreError("Failed to delete verification ticket") from exc

    def _key(self, email: str) -> str:
        return f"{self.key_prefix}{hash_token(email.lower())}"

    def _cooldown_key(self, email: str) -> str:
        return f"{self.cooldown_key_prefix}{hash_token(email.lower())}"

    def _ticket_key(self, token: str) -> str:
        return f"{self.ticket_key_prefix}{hash_token(token)}"
