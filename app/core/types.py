from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer


def _as_utc(value: datetime) -> datetime:
    """naive datetime을 UTC로 간주해 tz-aware로 바꾼다.

    MySQL DATETIME 컬럼은 타임존 없이 저장돼 naive로 읽히는데, DB 서버 타임존이 UTC라
    값 자체는 UTC다. 그대로 직렬화하면 오프셋 없는 문자열이 돼 RFC 3339(date-time)를 위반하고,
    브라우저는 이를 로컬 시간으로 해석한다. 이미 aware인 값은 UTC로 정규화한다.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# 응답 스키마의 datetime 필드용 — `...Z`(UTC 오프셋 포함)로 직렬화된다
UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


# 응답 스키마의 금리(%) 필드용 — 계산은 Decimal로 하고 JSON에는 숫자(5.5)로 직렬화한다.
# Pydantic v2는 Decimal을 JSON에서 문자열("5.50")로 내보내 스펙의 `type: number`를 위반한다(#64).
# 금리는 NUMERIC(4,2)라 float 변환으로 표시상 손실이 없다.
DecimalNumber = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


# 급여·고정지출 등 월 금액 입력 상한(원). 금액 컬럼(users·fixed_expenses·simulation_state·turns)이 모두
# 32bit INT(최대 약 21억)인데, cash_balance는 24턴 동안 급여가 누적되므로 INT 한계가 아니라
# 24턴 누적(최대 12억)이 범위 안에 드는 값으로 정한다 (spec#19, #74).
MAX_MONTHLY_AMOUNT = 50_000_000
