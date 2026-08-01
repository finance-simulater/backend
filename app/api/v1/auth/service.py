from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth.email_verification_service import (
    EmailVerificationResult,
    EmailVerificationService,
)
from app.api.v1.auth.email_verification_repository import (
    EmailVerificationRepository,
)
from app.api.v1.auth.refresh_token_repository import (
    RefreshTokenRepository,
    RefreshTokenStoreError,
)
from app.api.v1.auth.schema import (
    EmailVerificationRequest,
    LoginRequest,
    SignupRequest,
    TokenResponse,
)
from app.api.v1.user.model import User
from app.api.v1.user.repository import UserRepository
from app.api.v1.user.schema import UserCreate
from app.cache import redis_client
from app.core.config import settings
from app.core.email import get_email_sender
from app.core.exceptions import (
    conflict,
    forbidden,
    service_unavailable,
    unauthorized,
)
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)


@dataclass(frozen=True)
class AuthResult:
    user: User
    tokens: TokenResponse
    refresh_token: str


class AuthService:
    def __init__(
        self,
        db: Session,
        user_repository: UserRepository | None = None,
        refresh_token_repository: RefreshTokenRepository | None = None,
        email_verification_service: EmailVerificationService | None = None,
    ) -> None:
        self.user_repository = user_repository or UserRepository(db)
        self.refresh_token_repository = (
            refresh_token_repository or RefreshTokenRepository(redis_client)
        )
        self.email_verification_service = (
            email_verification_service
            or EmailVerificationService(
                user_repository=self.user_repository,
                verification_repository=EmailVerificationRepository(redis_client),
                email_sender=get_email_sender(),
            )
        )

    def signup(self, signup_request: SignupRequest) -> AuthResult:
        email = str(signup_request.email).lower()
        self.email_verification_service.assert_valid_ticket(
            email,
            signup_request.email_verification_token,
        )
        if self.user_repository.find_by_email(email) is not None:
            raise conflict("Email already exists", "EMAIL_ALREADY_EXISTS")
        if self.user_repository.find_by_nickname(signup_request.nickname) is not None:
            raise conflict("Nickname already exists", "NICKNAME_ALREADY_EXISTS")

        user_create = UserCreate(
            email=email,
            password=signup_request.password,
            nickname=signup_request.nickname,
            profile_image_seed=signup_request.profile_image_seed,
            job_type=signup_request.job_type,
            monthly_salary=signup_request.monthly_salary,
            provider="local",
        )
        try:
            user = self.user_repository.create(
                user_create,
                password_hash=hash_password(signup_request.password),
                is_email_verified=True,
            )
        except IntegrityError as exc:
            raise conflict(
                "Email or nickname already exists",
                "USER_ALREADY_EXISTS",
            ) from exc
        self.email_verification_service.consume_ticket(
            signup_request.email_verification_token
        )
        return self._issue_tokens(user)

    def login(self, login_request: LoginRequest) -> AuthResult:
        user = self.user_repository.find_by_email(str(login_request.email).lower())
        candidate_hash = (
            user.password
            if user is not None
            and user.provider == "local"
            and user.password is not None
            else DUMMY_PASSWORD_HASH
        )
        password_matches = verify_password(
            login_request.password,
            candidate_hash,
        )
        if (
            user is None
            or user.provider != "local"
            or user.password is None
            or not password_matches
        ):
            raise unauthorized("Invalid email or password", "INVALID_CREDENTIALS")
        if not user.is_email_verified:
            raise forbidden("Email verification is required", "EMAIL_NOT_VERIFIED")

        return self._issue_tokens(user)

    def send_verification_email(self, email: str) -> None:
        self.email_verification_service.send(email)

    def verify_email(
        self,
        request: EmailVerificationRequest,
    ) -> EmailVerificationResult:
        return self.email_verification_service.verify(request)

    def refresh(self, refresh_token: str) -> AuthResult:
        try:
            user_id = self.refresh_token_repository.consume(refresh_token)
        except RefreshTokenStoreError as exc:
            raise service_unavailable("Authentication service is not ready") from exc
        if user_id is None:
            raise unauthorized("Invalid or expired refresh token", "INVALID_REFRESH_TOKEN")

        user = self.user_repository.find_by_id(user_id)
        if user is None:
            raise unauthorized("Invalid or expired refresh token", "INVALID_REFRESH_TOKEN")
        if not user.is_email_verified:
            raise forbidden("Email verification is required", "EMAIL_NOT_VERIFIED")

        return self._issue_tokens(user)

    def logout(self, refresh_token: str | None) -> None:
        if refresh_token is not None:
            try:
                self.refresh_token_repository.delete(refresh_token)
            except RefreshTokenStoreError as exc:
                raise service_unavailable("Authentication service is not ready") from exc

    def _issue_tokens(self, user: User) -> AuthResult:
        refresh_token = create_refresh_token()
        refresh_expires_in = settings.refresh_token_expire_days * 24 * 60 * 60
        try:
            self.refresh_token_repository.save(
                refresh_token,
                user.id,
                expires_in_seconds=refresh_expires_in,
            )
        except RefreshTokenStoreError as exc:
            raise service_unavailable("Authentication service is not ready") from exc
        tokens = TokenResponse(
            access_token=create_access_token(subject=user.id),
            expires_in=settings.access_token_expire_minutes * 60,
        )
        return AuthResult(user=user, tokens=tokens, refresh_token=refresh_token)
