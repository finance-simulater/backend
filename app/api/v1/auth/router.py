from fastapi import APIRouter, Depends

from app.api.v1.auth.schema import LoginRequest, TokenResponse
from app.api.v1.auth.service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def get_auth_service() -> AuthService:
    return AuthService()


@router.post("/login", response_model=TokenResponse)
async def login(
    login_request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.login(login_request)
