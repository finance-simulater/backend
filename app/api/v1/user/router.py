from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.user.schema import UserCreate, UserResponse
from app.api.v1.user.service import UserService
from app.database import get_db

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("/", response_model=list[UserResponse])
async def list_users(service: UserService = Depends(get_user_service)):
    return service.get_users()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, service: UserService = Depends(get_user_service)):
    return service.get_user(user_id)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_create: UserCreate,
    service: UserService = Depends(get_user_service),
):
    return service.create_user(user_create)
