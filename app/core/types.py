from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator


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
