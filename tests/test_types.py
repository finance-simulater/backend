"""응답 직렬화 공통 타입 테스트 (finance-simulater/backend#43, #64)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import BaseModel

from app.core.types import DecimalNumber, UtcDatetime

KST = timezone(timedelta(hours=9))


class _Model(BaseModel):
    at: UtcDatetime


def test_naive_datetime_is_treated_as_utc() -> None:
    model = _Model(at=datetime(2026, 10, 11, 12, 0))

    assert model.model_dump_json() == '{"at":"2026-10-11T12:00:00Z"}'


def test_aware_datetime_is_normalized_to_utc() -> None:
    model = _Model(at=datetime(2026, 10, 11, 21, 0, tzinfo=KST))

    assert model.model_dump_json() == '{"at":"2026-10-11T12:00:00Z"}'


class _RateModel(BaseModel):
    rate: DecimalNumber


def test_decimal_number_is_serialized_as_json_number() -> None:
    model = _RateModel(rate=Decimal("5.50"))

    assert model.model_dump_json() == '{"rate":5.5}'


def test_decimal_number_keeps_decimal_in_python_mode() -> None:
    # 서비스 계층 계산(금리 가산 등)은 Decimal 그대로 쓴다
    assert _RateModel(rate=Decimal("5.50")).model_dump()["rate"] == Decimal("5.50")
