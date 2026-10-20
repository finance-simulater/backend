"""API E2E 테스트 공통 설정 (#85).

실제 MySQL·Redis에 붙은 앱을 TestClient로 호출해 회원가입부터 24턴 완료까지 흐름 전체를 검증한다.
DB는 integration과 같은 테스트 DB를 쓰지만 요청마다 실제로 커밋되므로, 테스트가 만든 사용자는 끝난 뒤 지운다.
"""

import os
import uuid
from collections.abc import Generator
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.v1.auth import service as auth_service_module
from app.database import get_db
from app.main import app
from tests.integration.conftest import _cleanup_real_users, mysql_engine  # noqa: F401 — mysql_engine 픽스처 재사용

# 개발용 Redis(0번 DB)와 섞이지 않도록 E2E는 별도 DB 번호를 쓰고, 시작·종료 시 그 DB만 비운다.
E2E_REDIS_URL = os.environ.get("E2E_REDIS_URL", "redis://localhost:6379/15")
PASSWORD = "password123!"


class CapturingEmailSender:
    """인증번호를 메일로 보내지 않고 수신자별로 보관한다 — 테스트가 서버 로그 대신 여기서 읽는다."""

    def __init__(self) -> None:
        self.codes: dict[str, str] = {}

    def send_verification_code(self, recipient: str, code: str) -> None:
        self.codes[recipient] = code


@dataclass
class Account:
    client: TestClient
    email: str
    user_id: int


@dataclass
class E2EApi:
    sender: CapturingEmailSender
    created_user_ids: list[int] = field(default_factory=list)

    def new_client(self) -> TestClient:
        # refresh 쿠키가 Secure로 발급될 수 있어 https로 호출해야 쿠키가 다시 전송된다
        return TestClient(app, base_url="https://testserver")

    def verify_email(self, client: TestClient, email: str) -> str:
        assert client.post("/api/v1/auth/email/send", json={"email": email}).status_code == 202
        response = client.post("/api/v1/auth/email/verify", json={"email": email, "code": self.sender.codes[email]})
        assert response.status_code == 200, response.text
        return response.json()["email_verification_token"]

    def signup(self, monthly_salary: int = 3_000_000) -> Account:
        """이메일 인증 → 회원가입까지 마치고 access token이 붙은 클라이언트를 돌려준다."""
        client = self.new_client()
        unique = uuid.uuid4().hex[:12]
        email = f"e2e-{unique}@example.com"
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "email_verification_token": self.verify_email(client, email),
                "password": PASSWORD,
                "nickname": f"e2e-{unique}",
                "profile_image_seed": "seed",
                "job_type": "employee",
                "monthly_salary": monthly_salary,
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        self.created_user_ids.append(body["user"]["id"])
        client.headers["Authorization"] = f"Bearer {body['tokens']['access_token']}"
        return Account(client=client, email=email, user_id=body["user"]["id"])


@pytest.fixture(scope="session")
def e2e_redis() -> Generator[Redis, None, None]:
    client = Redis.from_url(E2E_REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    try:
        client.ping()
    except Exception as exc:
        pytest.skip(f"E2E용 Redis에 연결할 수 없습니다 (docker-compose redis 실행 필요): {exc}")
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def api(mysql_engine: Engine, e2e_redis: Redis, monkeypatch: pytest.MonkeyPatch) -> Generator[E2EApi, None, None]:  # noqa: F811
    sender = CapturingEmailSender()
    # AuthService가 모듈 import 시점의 redis_client·발송기를 쓰므로 그 모듈의 이름을 바꿔 끼운다
    monkeypatch.setattr(auth_service_module, "redis_client", e2e_redis)
    monkeypatch.setattr(auth_service_module, "get_email_sender", lambda: sender)

    def get_e2e_db() -> Generator[Session, None, None]:
        session = Session(bind=mysql_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = get_e2e_db
    e2e_api = E2EApi(sender=sender)
    yield e2e_api
    app.dependency_overrides.pop(get_db, None)
    _cleanup_real_users(mysql_engine, e2e_api.created_user_ids)
