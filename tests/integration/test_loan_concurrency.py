"""대출 신청 동시 요청 시나리오 동시성 테스트

`apply_for_loan`은 "활성 대출 존재 여부 체크 -> 생성" 사이에 애플리케이션
레벨 락이 없다. DB의 `uq_loans_one_active_per_user` unique 제약(활성 대출일 때만
값을 갖는 computed column)이 최종 방어선 역할을 하므로, 동시에 신청해도 활성
대출이 2건 이상 생기지는 않는다. 다만 그 제약 위반(IntegrityError)을 서비스
레이어가 잡아 409로 변환하지 않는다는 점은 이 테스트로 고정해두고, 별도 버그
이슈로 분리한다 (finance-simulater/backend#36).
"""

import threading

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.v1.loan.repository import LoanRepository
from app.api.v1.loan.service import LoanService
from tests.integration.concurrency import run_concurrently
from tests.integration.factories import make_simulation_state, make_user

pytestmark = pytest.mark.integration


def test_apply_for_loan_concurrent_requests_only_one_becomes_active(real_session_factory, monkeypatch):
    session_factory, created_user_ids = real_session_factory

    setup_session = session_factory()
    user = make_user(setup_session, monthly_salary=3_000_000)
    make_simulation_state(setup_session, user, cash_balance=5_000_000, credit_score=70)
    setup_session.commit()
    created_user_ids.append(user.id)
    user_id = user.id
    setup_session.close()

    # "활성 대출 없음" 체크가 두 스레드 모두 끝난 뒤에야 생성 단계로 넘어가도록 강제해,
    # 체크와 생성 사이의 race window를 매 실행마다 재현되게 만든다.
    rendezvous = threading.Barrier(2)
    original_find_active_by_user = LoanRepository.find_active_by_user

    def find_active_by_user_then_wait(self: LoanRepository, uid: int):
        result = original_find_active_by_user(self, uid)
        rendezvous.wait(timeout=5)
        return result

    monkeypatch.setattr(LoanRepository, "find_active_by_user", find_active_by_user_then_wait)

    def apply_loan():
        session = session_factory()
        try:
            loan = LoanService(session).apply_for_loan(user_id, principal=1_000_000, duration_months=6)
            return loan.id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    results = run_concurrently(apply_loan, apply_loan)

    successes = [r for r in results if isinstance(r, int)]
    failures = [r for r in results if isinstance(r, Exception)]

    # DB unique 제약이 최종 방어선 역할을 해 활성 대출은 정확히 1건만 생성된다.
    assert len(successes) == 1
    assert len(failures) == 1
    # 현재는 이 제약 위반이 409(LOAN_ALREADY_ACTIVE)가 아니라 IntegrityError로 그대로
    # 샌다. 서비스 레이어에서 잡아 conflict()로 변환하도록 고치면 이 assert와 아래
    # 모듈 docstring을 함께 업데이트할 것 (#36 참고).
    assert isinstance(failures[0], IntegrityError)

    verify_session = session_factory()
    try:
        loans = LoanRepository(verify_session).find_all_by_user(user_id)
    finally:
        verify_session.close()

    assert len(loans) == 1
    assert loans[0].status == "active"
