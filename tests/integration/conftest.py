"""Repository 통합 테스트 인프라

실제 MySQL(docker-compose의 mysql 서비스)에 붙어 alembic 마이그레이션으로
스키마를 구성하고, 테스트마다 트랜잭션을 롤백해 상태를 격리한다. 테스트마다
반드시 롤백되므로 docker-compose의 MYSQL_DATABASE를 그대로 재사용해도 안전하다
— 별도 DB나 GRANT를 새로 만들 필요가 없다.

주의: `app.core.config.settings.database_url`은 절대 사용하지 않는다 — 이 값은
개발 환경에서 원격 RDS를 가리킬 수 있어, 실수로 실제 DB에 테스트가 붙는 사고를
막기 위해 `.env`의 docker-compose mysql 값(MYSQL_USER 등)으로 직접 조합한 URL만
사용한다.
"""

import os
from collections.abc import Callable, Generator
from urllib.parse import quote_plus, urlsplit, urlunsplit

import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _test_database_url() -> str:
    # .env의 docker-compose mysql 설정(MYSQL_USER 등)을 그대로 재사용해 조합한다.
    env_values = {**dotenv_values(os.path.join(BACKEND_ROOT, ".env")), **os.environ}
    user = env_values.get("MYSQL_USER")
    password = env_values.get("MYSQL_PASSWORD")
    if not user or not password:
        raise RuntimeError(
            "MYSQL_USER/MYSQL_PASSWORD가 .env에 없습니다. docker-compose mysql용 값을 "
            "먼저 설정하세요."
        )
    port = env_values.get("MYSQL_PORT", "3306")
    database = env_values.get("MYSQL_DATABASE", "finance")
    return f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@localhost:{port}/{database}"


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


# 사용자별로 실제 커밋된 데이터를 남기는 테이블. FK 의존 순서(자식 -> 부모)대로 정리한다.
_USER_OWNED_TABLES_BY_LOAN = ["repayment_schedule"]
_USER_OWNED_TABLES = ["loans", "turns", "expenses", "credit_history", "simulation_state"]


def _cleanup_real_users(engine: Engine, user_ids: list[int]) -> None:
    if not user_ids:
        return
    with engine.begin() as connection:
        for table in _USER_OWNED_TABLES_BY_LOAN:
            connection.execute(
                text(
                    f"DELETE FROM {table} WHERE loan_id IN "
                    "(SELECT id FROM loans WHERE user_id IN :ids)"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": user_ids},
            )
        for table in _USER_OWNED_TABLES:
            connection.execute(
                text(f"DELETE FROM {table} WHERE user_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": user_ids},
            )
        connection.execute(
            text("DELETE FROM users WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
            {"ids": user_ids},
        )


@pytest.fixture
def real_session_factory(mysql_engine: Engine) -> Generator[tuple[Callable[[], Session], list[int]], None, None]:
    """동시성 테스트 전용: 실제로 커밋되는 독립 세션을 스레드마다 생성한다.

    `db_session`과 달리 롤백되지 않으므로, 반환된 `created_user_ids` 리스트에
    테스트가 생성한 user id를 채워 넣으면 테스트 종료 후 자동으로 정리된다.
    """
    sessions: list[Session] = []
    created_user_ids: list[int] = []

    def factory() -> Session:
        session = Session(bind=mysql_engine)
        sessions.append(session)
        return session

    yield factory, created_user_ids

    for session in sessions:
        session.close()
    _cleanup_real_users(mysql_engine, created_user_ids)
