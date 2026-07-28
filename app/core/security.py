import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


class InvalidAccessTokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(password, hashed_password)
    except Exception:
        return False


def create_access_token(subject: int) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(subject),
        "type": "access",
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "access":
            raise InvalidAccessTokenError("Invalid token type")
        return int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError("Invalid or expired access token") from exc


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_email_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def create_email_verification_token() -> str:
    return secrets.token_urlsafe(32)


def hash_email_verification_code(email: str, code: str) -> str:
    message = f"{email.lower()}:{code}".encode("utf-8")
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
