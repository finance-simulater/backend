from unittest.mock import MagicMock

import pytest

from app.api.v1.auth.email_verification_repository import (
    EmailVerificationRecord,
    EmailVerificationRepository,
)
from app.api.v1.auth.email_verification_service import EmailVerificationService
from app.api.v1.auth.schema import EmailVerificationRequest
from app.api.v1.user.repository import UserRepository
from app.core.email import EmailDeliveryError, EmailSender
from app.core.exceptions import AppHTTPException
from app.core.security import hash_email_verification_code


def test_send_email_verification_saves_code_and_sends_email() -> None:
    user_repository = MagicMock(spec=UserRepository)
    verification_repository = MagicMock(spec=EmailVerificationRepository)
    email_sender = MagicMock(spec=EmailSender)
    user_repository.find_by_email.return_value = None
    verification_repository.reserve_send.return_value = True
    service = EmailVerificationService(
        user_repository=user_repository,
        verification_repository=verification_repository,
        email_sender=email_sender,
    )

    service.send("user@example.com")

    verification_repository.save.assert_called_once()
    sent_code = email_sender.send_verification_code.call_args.args[1]
    assert sent_code.isdigit()
    assert len(sent_code) == 6


def test_send_existing_email_returns_without_revealing_registration() -> None:
    user_repository = MagicMock(spec=UserRepository)
    verification_repository = MagicMock(spec=EmailVerificationRepository)
    email_sender = MagicMock(spec=EmailSender)
    user_repository.find_by_email.return_value = object()
    verification_repository.reserve_send.return_value = True
    service = EmailVerificationService(
        user_repository=user_repository,
        verification_repository=verification_repository,
        email_sender=email_sender,
    )

    service.send("user@example.com")

    verification_repository.reserve_send.assert_called_once()
    verification_repository.save.assert_not_called()
    email_sender.send_verification_code.assert_not_called()


def test_send_rate_limit_rejects_request_without_sending() -> None:
    user_repository = MagicMock(spec=UserRepository)
    verification_repository = MagicMock(spec=EmailVerificationRepository)
    email_sender = MagicMock(spec=EmailSender)
    user_repository.find_by_email.return_value = None
    verification_repository.reserve_send.return_value = False
    service = EmailVerificationService(
        user_repository=user_repository,
        verification_repository=verification_repository,
        email_sender=email_sender,
    )

    with pytest.raises(AppHTTPException) as exc_info:
        service.send("user@example.com")

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "VERIFICATION_EMAIL_RATE_LIMITED"
    verification_repository.save.assert_not_called()
    email_sender.send_verification_code.assert_not_called()


def test_email_delivery_failure_removes_verification_code() -> None:
    user_repository = MagicMock(spec=UserRepository)
    verification_repository = MagicMock(spec=EmailVerificationRepository)
    email_sender = MagicMock(spec=EmailSender)
    user_repository.find_by_email.return_value = None
    verification_repository.reserve_send.return_value = True
    email_sender.send_verification_code.side_effect = EmailDeliveryError(
        "ses down"
    )
    service = EmailVerificationService(
        user_repository=user_repository,
        verification_repository=verification_repository,
        email_sender=email_sender,
    )

    with pytest.raises(AppHTTPException) as exc_info:
        service.send("user@example.com")

    assert exc_info.value.status_code == 503
    verification_repository.delete.assert_called_once_with(
        "user@example.com",
        include_cooldown=True,
    )


def test_verify_email_issues_ticket_without_creating_user() -> None:
    email = "user@example.com"
    code = "123456"
    user_repository = MagicMock(spec=UserRepository)
    verification_repository = MagicMock(spec=EmailVerificationRepository)
    email_sender = MagicMock(spec=EmailSender)
    user_repository.find_by_email.return_value = None
    verification_repository.find.return_value = EmailVerificationRecord(
        code_hash=hash_email_verification_code(email, code),
        attempts=0,
    )
    service = EmailVerificationService(
        user_repository=user_repository,
        verification_repository=verification_repository,
        email_sender=email_sender,
    )

    result = service.verify(
        EmailVerificationRequest(email=email, code=code)
    )

    saved_ticket = verification_repository.save_ticket.call_args
    assert saved_ticket.args[0] == result.token
    assert saved_ticket.args[1] == email
    assert saved_ticket.kwargs["expires_in_seconds"] == result.expires_in
    verification_repository.delete.assert_called_once_with(
        email,
        include_cooldown=True,
    )
    user_repository.create.assert_not_called()
    assert len(result.token) >= 32


def test_verify_existing_email_returns_generic_invalid_code() -> None:
    email = "user@example.com"
    code = "123456"
    user_repository = MagicMock(spec=UserRepository)
    verification_repository = MagicMock(spec=EmailVerificationRepository)
    user_repository.find_by_email.return_value = object()
    verification_repository.find.return_value = EmailVerificationRecord(
        code_hash=hash_email_verification_code(email, code),
        attempts=0,
    )
    service = EmailVerificationService(
        user_repository=user_repository,
        verification_repository=verification_repository,
        email_sender=MagicMock(spec=EmailSender),
    )

    with pytest.raises(AppHTTPException) as exc_info:
        service.verify(EmailVerificationRequest(email=email, code=code))

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_VERIFICATION_CODE"
    verification_repository.save_ticket.assert_not_called()


def test_verify_email_increments_attempts_for_wrong_code() -> None:
    email = "user@example.com"
    user_repository = MagicMock(spec=UserRepository)
    verification_repository = MagicMock(spec=EmailVerificationRepository)
    user_repository.find_by_email.return_value = None
    verification_repository.find.return_value = EmailVerificationRecord(
        code_hash=hash_email_verification_code(email, "123456"),
        attempts=0,
    )
    verification_repository.increment_attempts.return_value = 1
    service = EmailVerificationService(
        user_repository=user_repository,
        verification_repository=verification_repository,
        email_sender=MagicMock(spec=EmailSender),
    )

    with pytest.raises(AppHTTPException) as exc_info:
        service.verify(
            EmailVerificationRequest(email=email, code="654321")
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_VERIFICATION_CODE"
    verification_repository.increment_attempts.assert_called_once_with(email)
