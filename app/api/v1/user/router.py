from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.user.model import User
from app.api.v1.user.schema import UserResponse, UserUpdate
from app.api.v1.user.service import UserService
from app.database import get_db

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: UserUpdate,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return service.update_me(current_user, request)
