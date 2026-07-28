import logging
from functools import lru_cache
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


class EmailSender(Protocol):
    def send_verification_code(self, recipient: str, code: str) -> None: ...


class ConsoleEmailSender:
    def send_verification_code(self, recipient: str, code: str) -> None:
        logger.warning(
            "Email verification code for %s: %s",
            recipient,
            code,
        )


class SesEmailSender:
    def __init__(self) -> None:
        self.client = boto3.client("sesv2", region_name=settings.aws_region)

    def send_verification_code(self, recipient: str, code: str) -> None:
        subject = "[Finance Simulator] 이메일 인증번호"
        text_body = (
            f"이메일 인증번호는 {code}입니다.\n"
            f"{settings.email_verification_ttl_minutes}분 안에 입력해 주세요."
        )
        html_body = (
            "<h2>이메일 인증</h2>"
            f"<p>인증번호는 <strong>{code}</strong>입니다.</p>"
            f"<p>{settings.email_verification_ttl_minutes}분 안에 입력해 주세요.</p>"
        )

        try:
            self.client.send_email(
                FromEmailAddress=str(settings.email_from_address),
                Destination={"ToAddresses": [recipient]},
                Content={
                    "Simple": {
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {
                            "Text": {"Data": text_body, "Charset": "UTF-8"},
                            "Html": {"Data": html_body, "Charset": "UTF-8"},
                        },
                    }
                },
            )
        except (BotoCoreError, ClientError) as exc:
            raise EmailDeliveryError("Failed to send verification email") from exc


@lru_cache
def get_email_sender() -> EmailSender:
    if settings.email_provider == "ses":
        return SesEmailSender()
    return ConsoleEmailSender()
