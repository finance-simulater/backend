"""동시성 통합 테스트 유틸리티

`db_session`은 테스트마다 하나의 커넥션 위에서 SAVEPOINT로 격리하기 때문에
여러 스레드가 진짜로 동시에 커밋하는 상황(락 대기, race condition)을 재현할 수
없다. 이 모듈은 스레드마다 독립된 커넥션/세션을 실제로 커밋시켜 그 상황을
재현하기 위한 것이다.
"""

import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def run_concurrently(*fns: Callable[[], T]) -> list[T | Exception]:
    """각 함수를 별도 스레드에서 barrier로 시작 시점을 맞춰 동시에 실행한다.

    각 함수가 예외를 던지면 결과 리스트의 해당 위치에 그 예외 인스턴스를 담는다
    (raise하지 않음) — 두 함수 중 하나만 실패하는 시나리오(예: unique 제약 충돌)를
    검증하기 위함.
    """
    barrier = threading.Barrier(len(fns))
    results: list[T | Exception | None] = [None] * len(fns)

    def run(index: int, fn: Callable[[], T]) -> None:
        barrier.wait()
        try:
            results[index] = fn()
        except Exception as exc:  # noqa: BLE001 - 테스트에서 예외 종류를 직접 검증
            results[index] = exc

    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(fns)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    # 각 스레드가 자기 인덱스를 반드시 덮어쓰므로 이 시점엔 None이 남아있지 않다 —
    # 반환 타입(list[T | Exception])과 results의 선언 타입을 일치시킨다.
    assert None not in results
    return results  # type: ignore[return-value]
