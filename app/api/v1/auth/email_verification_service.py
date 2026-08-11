from dataclasses import dataclass
from secrets import compare_digest

from app.api.v1.auth.email_verification_repository import (
    EmailVerificationRepository,
    VerificationStoreError,
)
from app.api.v1.auth.schema import EmailVerificationRequest
from app.api.v1.user.repository import UserRepository
from app.core.config import settings
from app.core.email import EmailDeliveryError, EmailSender
from app.core.exceptions import (
    bad_request,
    service_unavailable,
    too_many_requests,
)
from app.core.security import (
    create_email_verification_code,
    create_email_verification_token,
    hash_email_verification_code,
)


@dataclass(frozen=True)
class EmailVerificationResult:
    token: str
    expires_in: int


class EmailVerificationService:
    def __init__(
        self,
        user_repository: UserRepository,
        verification_repository: EmailVerificationRepository,
        email_sender: EmailSender,
    ) -> None:
        self.user_repository = user_repository
        self.verification_repository = verification_repository
        self.email_sender = email_sender

    @property
    def expires_in_seconds(self) -> int:
        return settings.email_verification_ttl_minutes * 60

    @property
    def ticket_expires_in_seconds(self) -> int:
        return settings.email_verification_ticket_ttl_minutes * 60

    def send(self, email: str) -> None:
        normalized_email = email.lower()

        try:
            reserved = self.verification_repository.reserve_send(
                normalized_email,
                cooldown_seconds=settings.email_resend_cooldown_seconds,
            )
            if not reserved:
                raise too_many_requests(
                    "Please wait before requesting another verification email",
                    "VERIFICATION_EMAIL_RATE_LIMITED",
                )

            if self.user_repository.find_by_email(normalized_email) is not None:
                return

            code = create_email_verification_code()
            self.verification_repository.save(
                normalized_email,
                hash_email_verification_code(normalized_email, code),
                expires_in_seconds=self.expires_in_seconds,
            )
        except VerificationStoreError as exc:
            raise service_unavailable("Email verification service is not ready") from exc

        try:
            self.email_sender.send_verification_code(normalized_email, code)
        except EmailDeliveryError as exc:
            try:
                self.verification_repository.delete(
                    normalized_email,
                    include_cooldown=True,
                )
            except VerificationStoreError:
                pass
            raise service_unavailable("Failed to send verification email") from exc

    def verify(self, request: EmailVerificationRequest) -> EmailVerificationResult:
        email = str(request.email).lower()
        user_exists = self.user_repository.find_by_email(email) is not None

        try:
            record = self.verification_repository.find(email)
        except VerificationStoreError as exc:
            raise service_unavailable("Email verification service is not ready") from exc

        if user_exists or record is None:
            raise self._invalid_code()
        if record.attempts >= settings.email_verification_max_attempts:
            raise self._attempts_exceeded()

        submitted_hash = hash_email_verification_code(email, request.code)
        if not compare_digest(record.code_hash, submitted_hash):
            self._handle_wrong_code(email)

        token = create_email_verification_token()
        try:
            self.verification_repository.save_ticket(
                token,
                email,
                expires_in_seconds=self.ticket_expires_in_seconds,
            )
            self.verification_repository.delete(email, include_cooldown=True)
        except VerificationStoreError as exc:
            raise service_unavailable("Email verification service is not ready") from exc
        return EmailVerificationResult(
            token=token,
            expires_in=self.ticket_expires_in_seconds,
        )

    def assert_valid_ticket(self, email: str, token: str) -> None:
        try:
            verified_email = self.verification_repository.find_ticket_email(token)
        except VerificationStoreError as exc:
            raise service_unavailable("Email verification service is not ready") from exc

        if verified_email is None or not compare_digest(
            verified_email,
            email.lower(),
        ):
            raise bad_request(
                "Email verification is required",
                "EMAIL_VERIFICATION_REQUIRED",
            )

    def consume_ticket(self, token: str) -> None:
        try:
            self.verification_repository.delete_ticket(token)
        except VerificationStoreError as exc:
            raise service_unavailable("Email verification service is not ready") from exc

    def _handle_wrong_code(self, email: str) -> None:
        try:
            attempts = self.verification_repository.increment_attempts(email)
            if attempts >= settings.email_verification_max_attempts:
                self.verification_repository.delete(email)
                raise self._attempts_exceeded()
        except VerificationStoreError as exc:
            raise service_unavailable("Email verification service is not ready") from exc
        raise self._invalid_code()

    @staticmethod
    def _invalid_code():
        return bad_request(
            "Invalid or expired verification code",
            "INVALID_VERIFICATION_CODE",
        )

    @staticmethod
    def _attempts_exceeded():
        return too_many_requests(
            "Verification attempt limit exceeded",
            "VERIFICATION_ATTEMPTS_EXCEEDED",
        )
