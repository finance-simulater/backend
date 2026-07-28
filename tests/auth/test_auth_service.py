from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.api.v1.auth.email_verification_service import EmailVerificationService
from app.api.v1.auth.refresh_token_repository import (
    RefreshTokenRepository,
    RefreshTokenStoreError,
)
from app.api.v1.auth.schema import LoginRequest, SignupRequest
from app.api.v1.auth.service import AuthService
from app.api.v1.user.repository import UserRepository
from app.core.config import settings
from app.core.exceptions import AppHTTPException
from tests.auth.factories import make_user


def test_signup_creates_verified_user_after_ticket_validation() -> None:
    user_repository = MagicMock(spec=UserRepository)
    refresh_repository = MagicMock(spec=RefreshTokenRepository)
    verification_service = MagicMock(spec=EmailVerificationService)
    user_repository.find_by_email.return_value = None
    user_repository.find_by_nickname.return_value = None
    user_repository.create.return_value = make_user(is_email_verified=True)
    service = AuthService(
        db=MagicMock(),
        user_repository=user_repository,
        refresh_token_repository=refresh_repository,
        email_verification_service=verification_service,
    )

    result = service.signup(
        SignupRequest(
            email="user@example.com",
            email_verification_token="v" * 43,
            password="password123",
            nickname="tester",
            profile_image_seed="tester",
            job_type="employee",
            monthly_salary=3_000_000,
        )
    )

    create_call = user_repository.create.call_args
    assert create_call.kwargs["password_hash"] != "password123"
    assert create_call.kwargs["is_email_verified"] is True
    assert create_call.args[0].password == "password123"
    assert result.user.id == 1
    verification_service.assert_valid_ticket.assert_called_once_with(
        "user@example.com",
        "v" * 43,
    )
    verification_service.consume_ticket.assert_called_once_with("v" * 43)
    refresh_repository.save.assert_called_once()


def test_signup_does_not_create_user_when_verification_ticket_is_invalid() -> None:
    user_repository = MagicMock(spec=UserRepository)
    verification_service = MagicMock(spec=EmailVerificationService)
    user_repository.find_by_email.return_value = None
    user_repository.find_by_nickname.return_value = None
    verification_service.assert_valid_ticket.side_effect = AppHTTPException(
        status_code=400,
        detail="Email verification is required",
        code="EMAIL_VERIFICATION_REQUIRED",
    )
    service = AuthService(
        db=MagicMock(),
        user_repository=user_repository,
        refresh_token_repository=MagicMock(spec=RefreshTokenRepository),
        email_verification_service=verification_service,
    )

    with pytest.raises(AppHTTPException) as exc_info:
        service.signup(
            SignupRequest(
                email="user@example.com",
                email_verification_token="v" * 43,
                password="password123",
                nickname="tester",
                profile_image_seed="tester",
                job_type="employee",
                monthly_salary=3_000_000,
            )
        )

    assert exc_info.value.code == "EMAIL_VERIFICATION_REQUIRED"
    user_repository.find_by_email.assert_not_called()
    user_repository.find_by_nickname.assert_not_called()
    user_repository.create.assert_not_called()
    verification_service.consume_ticket.assert_not_called()


def test_signup_rejects_duplicate_email() -> None:
    user_repository = MagicMock(spec=UserRepository)
    verification_service = MagicMock(spec=EmailVerificationService)
    user_repository.find_by_email.return_value = make_user()
    service = AuthService(
        db=MagicMock(),
        user_repository=user_repository,
        refresh_token_repository=MagicMock(spec=RefreshTokenRepository),
        email_verification_service=verification_service,
    )

    with pytest.raises(AppHTTPException) as exc_info:
        service.signup(
            SignupRequest(
                email="user@example.com",
                email_verification_token="v" * 43,
                password="password123",
                nickname="tester",
                profile_image_seed="tester",
                job_type="employee",
                monthly_salary=3_000_000,
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "EMAIL_ALREADY_EXISTS"
    verification_service.assert_valid_ticket.assert_called_once()


def test_login_rejects_invalid_password() -> None:
    user_repository = MagicMock(spec=UserRepository)
    user_repository.find_by_email.return_value = make_user()
    service = AuthService(
        db=MagicMock(),
        user_repository=user_repository,
        refresh_token_repository=MagicMock(spec=RefreshTokenRepository),
    )

    with pytest.raises(AppHTTPException) as exc_info:
        service.login(LoginRequest(email="user@example.com", password="wrong-password"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "INVALID_CREDENTIALS"


def test_login_unknown_email_runs_dummy_password_verification() -> None:
    user_repository = MagicMock(spec=UserRepository)
    user_repository.find_by_email.return_value = None
    service = AuthService(
        db=MagicMock(),
        user_repository=user_repository,
        refresh_token_repository=MagicMock(spec=RefreshTokenRepository),
    )

    with patch(
        "app.api.v1.auth.service.verify_password",
        return_value=False,
    ) as verify:
        with pytest.raises(AppHTTPException) as exc_info:
            service.login(
                LoginRequest(
                    email="missing@example.com",
                    password="wrong-password",
                )
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "INVALID_CREDENTIALS"
    verify.assert_called_once()


def test_login_rejects_unverified_email() -> None:
    user_repository = MagicMock(spec=UserRepository)
    user_repository.find_by_email.return_value = make_user(
        is_email_verified=False
    )
    service = AuthService(
        db=MagicMock(),
        user_repository=user_repository,
        refresh_token_repository=MagicMock(spec=RefreshTokenRepository),
    )

    with pytest.raises(AppHTTPException) as exc_info:
        service.login(
            LoginRequest(email="user@example.com", password="password123")
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "EMAIL_NOT_VERIFIED"


def test_login_issues_valid_access_token() -> None:
    user_repository = MagicMock(spec=UserRepository)
    refresh_repository = MagicMock(spec=RefreshTokenRepository)
    user_repository.find_by_email.return_value = make_user()
    service = AuthService(
        db=MagicMock(),
        user_repository=user_repository,
        refresh_token_repository=refresh_repository,
    )

    result = service.login(
        LoginRequest(email="user@example.com", password="password123")
    )
    payload = jwt.decode(
        result.tokens.access_token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == "1"
    assert payload["type"] == "access"
    refresh_repository.save.assert_called_once()


def test_refresh_rotates_refresh_token() -> None:
    user_repository = MagicMock(spec=UserRepository)
    refresh_repository = MagicMock(spec=RefreshTokenRepository)
    refresh_repository.consume.return_value = 1
    user_repository.find_by_id.return_value = make_user()
    service = AuthService(
        db=MagicMock(),
        user_repository=user_repository,
        refresh_token_repository=refresh_repository,
    )

    result = service.refresh("old-refresh-token")

    refresh_repository.consume.assert_called_once_with("old-refresh-token")
    refresh_repository.save.assert_called_once()
    assert result.refresh_token != "old-refresh-token"


def test_refresh_store_failure_returns_service_unavailable() -> None:
    refresh_repository = MagicMock(spec=RefreshTokenRepository)
    refresh_repository.consume.side_effect = RefreshTokenStoreError("redis down")
    service = AuthService(
        db=MagicMock(),
        user_repository=MagicMock(spec=UserRepository),
        refresh_token_repository=refresh_repository,
    )

    with pytest.raises(AppHTTPException) as exc_info:
        service.refresh("refresh-token")

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "SERVICE_UNAVAILABLE"
