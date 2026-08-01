from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.auth.schema import (
    EmailVerificationRequest,
    EmailVerificationResponse,
    EmailVerificationSendRequest,
    LoginRequest,
    MessageResponse,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)
from app.api.v1.auth.service import AuthService
from app.api.v1.user.model import User
from app.api.v1.user.schema import UserResponse
from app.core.config import settings
from app.core.exceptions import unauthorized
from app.database import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


def delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/api/v1/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(
    signup_request: SignupRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    result = service.signup(signup_request)
    set_refresh_cookie(response, result.refresh_token)
    return SignupResponse(
        user=result.user,
        tokens=result.tokens,
    )


@router.post(
    "/email/send",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def send_verification_email(
    send_request: EmailVerificationSendRequest,
    service: AuthService = Depends(get_auth_service),
):
    service.send_verification_email(str(send_request.email))
    return MessageResponse(message="Verification email has been sent")


@router.post("/email/verify", response_model=EmailVerificationResponse)
def verify_email(
    verification_request: EmailVerificationRequest,
    service: AuthService = Depends(get_auth_service),
):
    result = service.verify_email(verification_request)
    return EmailVerificationResponse(
        email_verification_token=result.token,
        expires_in=result.expires_in,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    login_request: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    result = service.login(login_request)
    set_refresh_cookie(response, result.refresh_token)
    return result.tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token is None:
        raise unauthorized("Refresh token is required", "REFRESH_TOKEN_REQUIRED")

    result = service.refresh(refresh_token)
    set_refresh_cookie(response, result.refresh_token)
    return result.tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> None:
    service.logout(request.cookies.get(settings.refresh_cookie_name))
    delete_refresh_cookie(response)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
