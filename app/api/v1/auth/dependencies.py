from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.v1.user.model import User
from app.api.v1.user.repository import UserRepository
from app.core.exceptions import unauthorized
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.database import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized("Authentication is required")

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidAccessTokenError as exc:
        raise unauthorized("Invalid or expired access token") from exc

    user = UserRepository(db).find_by_id(user_id)
    if user is None:
        raise unauthorized("Invalid or expired access token")
    return user
