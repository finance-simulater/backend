"""응답 datetime UTC 직렬화 공통 타입 테스트 (finance-simulater/backend#43)."""

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from app.core.types import UtcDatetime

KST = timezone(timedelta(hours=9))


class _Model(BaseModel):
    at: UtcDatetime


def test_naive_datetime_is_treated_as_utc() -> None:
    model = _Model(at=datetime(2026, 10, 11, 12, 0))

    assert model.model_dump_json() == '{"at":"2026-10-11T12:00:00Z"}'


def test_aware_datetime_is_normalized_to_utc() -> None:
    model = _Model(at=datetime(2026, 10, 11, 21, 0, tzinfo=KST))

    assert model.model_dump_json() == '{"at":"2026-10-11T12:00:00Z"}'
