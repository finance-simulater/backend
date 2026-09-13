"""Repository 통합 테스트 인프라 (finance-simulater/backend#31).

실제 MySQL(docker-compose의 mysql 서비스)에 붙어 alembic 마이그레이션으로
스키마를 구성하고, 테스트마다 트랜잭션을 롤백해 상태를 격리한다. 테스트마다
반드시 롤백되므로 docker-compose의 MYSQL_DATABASE를 그대로 재사용해도 안전하다
— 별도 DB나 GRANT를 새로 만들 필요가 없다.

주의: `app.core.config.settings.database_url`은 절대 사용하지 않는다 — 이 값은
개발 환경에서 원격 RDS를 가리킬 수 있어, 실수로 실제 DB에 테스트가 붙는 사고를
막기 위해 통합 테스트 전용 `TEST_DATABASE_URL` 환경변수만 사용한다.
"""

import os
from collections.abc import Generator
from urllib.parse import urlsplit, urlunsplit

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL 환경변수가 설정되지 않았습니다. "
            "통합 테스트는 settings.database_url을 사용하지 않습니다 "
            "(원격 DB 오염 방지). docker-compose mysql을 띄운 뒤 "
            "TEST_DATABASE_URL=mysql+pymysql://<MYSQL_USER>:<MYSQL_PASSWORD>@localhost:<MYSQL_PORT>/<MYSQL_DATABASE> "
            "형태로, .env의 docker-compose mysql 값 그대로 지정하세요."
        )
    return url


def _create_database_if_missing(database_url: str) -> None:
    parts = urlsplit(database_url)
    db_name = parts.path.lstrip("/")
    server_url = urlunsplit(parts._replace(path="/"))

    server_engine = create_engine(server_url)
    try:
        with server_engine.connect() as connection:
            connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
            connection.commit()
    finally:
        server_engine.dispose()


@pytest.fixture(scope="session")
def mysql_engine() -> Generator[Engine, None, None]:
    database_url = _test_database_url()

    try:
        _create_database_if_missing(database_url)
    except OperationalError as exc:
        pytest.skip(f"테스트용 MySQL에 연결할 수 없습니다 (docker-compose mysql 실행 필요): {exc}")

    alembic_cfg = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(BACKEND_ROOT, "alembic"))
    # alembic/env.py가 settings.database_url(원격일 수 있음) 대신 이 값을 쓰도록 강제한다.
    alembic_cfg.attributes["sqlalchemy_url"] = database_url
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(mysql_engine: Engine) -> Generator[Session, None, None]:
    connection = mysql_engine.connect()
    transaction = connection.begin()

    # repository 코드가 내부에서 db.commit()을 호출해도 SAVEPOINT만 release/재생성될 뿐,
    # 위의 outer transaction은 살아있는 상태로 유지된다.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
