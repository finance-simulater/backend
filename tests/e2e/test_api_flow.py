"""회원가입부터 24턴 완료까지 API 흐름 E2E 테스트 (#85).

각 테스트는 새 사용자로 시작해 기획 흐름(가입 → 월급 → 소비 체크 → 모의투자 → 대출 → 상환)을 실제 MySQL·Redis
위에서 진행한다. 금액 기대값은 소비 수준별 지출 비율(save 5% · normal 10%, 카테고리 3개)과
가입 시 시작 현금(= 월급)으로 계산한다.
"""

from datetime import date

import httpx2
import pytest

from app.api.v1.auth import service as auth_service_module
from tests.e2e.conftest import PASSWORD, E2EApi

pytestmark = pytest.mark.e2e

TURNS = "/api/v1/simulation/turns"
FIXED_EXPENSES = "/api/v1/users/me/fixed-expenses"
NORMAL = {"food_choice": "normal", "shopping_choice": "normal", "leisure_choice": "normal"}
SAVE = {"food_choice": "save", "shopping_choice": "save", "leisure_choice": "save"}


def expect(response: httpx2.Response, status_code: int) -> dict:
    """준비 단계 호출이 실패하면 뒤쪽 assert 대신 여기서 요청·응답 본문과 함께 실패시킨다."""
    assert response.status_code == status_code, (
        f"{response.request.method} {response.request.url.path} → {response.status_code}: {response.text}"
    )
    return response.json()


# ── 인증 ────────────────────────────────────────


def test_signup_login_refresh_logout(api: E2EApi) -> None:
    # 틀린 인증번호 거절만 확인하는 용도라 이 이메일로는 가입하지 않는다(남는 사용자 없음).
    # 정상 인증 → 가입 흐름은 아래 api.signup()이 새 이메일로 진행한다.
    client = api.new_client()
    email = "e2e-auth@example.com"
    assert client.post("/api/v1/auth/email/send", json={"email": email}).status_code == 202
    code = api.sender.codes[email]
    wrong_code = "000000" if code != "000000" else "111111"
    assert client.post("/api/v1/auth/email/verify", json={"email": email, "code": wrong_code}).status_code == 400
    account = api.signup()

    assert "refresh_token" in account.client.cookies
    assert account.client.get("/api/v1/auth/me").json()["email"] == account.email
    assert api.new_client().get("/api/v1/auth/me").status_code == 401

    login = api.new_client()
    assert login.post("/api/v1/auth/login", json={"email": account.email, "password": "wrong!"}).status_code == 401
    assert login.post("/api/v1/auth/login", json={"email": account.email, "password": PASSWORD}).status_code == 200

    refreshed = login.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    login.headers["Authorization"] = f"Bearer {refreshed.json()['access_token']}"
    assert login.post("/api/v1/auth/logout").status_code == 204
    assert login.post("/api/v1/auth/refresh").status_code == 401


# ── 급여·고정지출 ────────────────────────────────


def test_salary_and_fixed_expenses(api: E2EApi) -> None:
    client = api.signup().client

    assert client.patch("/api/v1/users/me", json={"monthly_salary": 3_500_000}).json()["monthly_salary"] == 3_500_000
    assert client.patch("/api/v1/users/me", json={"monthly_salary": 50_000_001}).status_code == 422

    rent = client.post(FIXED_EXPENSES, json={"name": " 월세 ", "amount": 600_000})
    assert (rent.status_code, rent.json()["name"]) == (201, "월세")
    phone = expect(client.post(FIXED_EXPENSES, json={"name": "통신비", "amount": 50_000}), 201)
    assert [item["name"] for item in client.get(FIXED_EXPENSES).json()] == ["월세", "통신비"]

    updated = client.patch(f"{FIXED_EXPENSES}/{phone['id']}", json={"amount": 55_000}).json()
    assert (updated["name"], updated["amount"]) == ("통신비", 55_000)
    assert client.patch(f"{FIXED_EXPENSES}/{phone['id']}", json={"amount": None}).status_code == 422
    assert client.delete(f"{FIXED_EXPENSES}/{phone['id']}").status_code == 204
    assert client.delete(f"{FIXED_EXPENSES}/{phone['id']}").status_code == 404


def test_fixed_expense_limit(api: E2EApi) -> None:
    client = api.signup().client
    for i in range(30):
        assert client.post(FIXED_EXPENSES, json={"name": f"항목{i}", "amount": 1_000}).status_code == 201

    response = client.post(FIXED_EXPENSES, json={"name": "31번째", "amount": 1_000})

    assert (response.status_code, response.json()["code"]) == (422, "FIXED_EXPENSE_LIMIT_EXCEEDED")


# ── 시뮬레이션(턴) ───────────────────────────────


def test_signup_starts_simulation_with_salary_from_next_month(api: E2EApi, monkeypatch: pytest.MonkeyPatch) -> None:
    # 월말 자정 근처 실행 시 달이 어긋나지 않게 가입일을 고정한다 — 12월 말이라 연도 넘김도 함께 확인
    monkeypatch.setattr(auth_service_module, "today_kst", lambda: date(2026, 12, 31))

    state = api.signup(monthly_salary=3_000_000).client.get("/api/v1/simulation").json()

    assert (state["current_year"], state["current_month"]) == (2027, 1)
    assert (state["current_turn"], state["cash_balance"], state["status"]) == (1, 3_000_000, "active")
    assert (state["credit_score"], state["consume_score"]) == (50, 50)


def test_turn_settles_balance_and_scores(api: E2EApi) -> None:
    client = api.signup(monthly_salary=3_000_000).client
    expect(client.post(FIXED_EXPENSES, json={"name": "월세", "amount": 600_000}), 201)

    first = expect(client.post(TURNS, json=NORMAL), 201)
    # 시작 300만 + 월급 300만 - 고정 60만 - 변동 300만 × 10% × 3
    assert (first["fixed_expense_total"], first["variable_expense_total"], first["cash_balance_after"]) == (
        600_000,
        900_000,
        4_500_000,
    )
    expect(client.post(TURNS, json=SAVE), 201)

    assert client.get("/api/v1/simulation").json()["consume_score"] == 50 + 2 * 3
    assert [turn["turn_number"] for turn in client.get(TURNS).json()] == [2, 1]
    assert client.get(f"{TURNS}/1").status_code == 200
    assert client.get(f"{TURNS}/99").status_code == 404


def test_turn_rejected_when_expenses_exceed_balance(api: E2EApi) -> None:
    client = api.signup(monthly_salary=1_000_000).client
    expect(client.post(FIXED_EXPENSES, json={"name": "큰 지출", "amount": 50_000_000}), 201)

    response = client.post(TURNS, json=SAVE)

    assert (response.status_code, response.json()["code"]) == (422, "INSUFFICIENT_BALANCE")
    assert client.get(TURNS).json() == []


def test_simulation_completes_after_24_turns(api: E2EApi) -> None:
    client = api.signup().client
    for _ in range(24):
        assert client.post(TURNS, json=SAVE).status_code == 201

    assert client.get("/api/v1/simulation").json()["status"] == "completed"
    response = client.post(TURNS, json=SAVE)
    assert (response.status_code, response.json()["code"]) == (409, "SIMULATION_ALREADY_COMPLETED")


# ── 주식 ────────────────────────────────────────


def test_stock_buy_and_sell(api: E2EApi) -> None:
    client = api.signup(monthly_salary=3_000_000).client

    bought = client.post("/api/v1/stocks/buy", json={"stock_type": "index", "amount": 500_000})
    assert (bought.status_code, bought.json()["cash_balance"]) == (201, 2_500_000)
    over_buy = client.post("/api/v1/stocks/buy", json={"stock_type": "high_vol", "amount": 999_999_999})
    assert over_buy.json()["code"] == "INSUFFICIENT_BALANCE"

    sold = client.post("/api/v1/stocks/sell", json={"stock_type": "index", "amount": 200_000}).json()
    assert (sold["holding"]["current_value"], sold["cash_balance"]) == (300_000, 2_700_000)
    over_sell = client.post("/api/v1/stocks/sell", json={"stock_type": "index", "amount": 9_000_000})
    assert over_sell.json()["code"] == "INSUFFICIENT_HOLDINGS"
    assert client.post("/api/v1/stocks/sell", json={"stock_type": "low_vol", "amount": 1}).status_code == 404


@pytest.mark.xfail(strict=True, reason="턴마다 평가액 갱신(몬테카를로)은 MVP 이후 구현 — #21")
def test_stock_value_changes_each_turn(api: E2EApi) -> None:
    client = api.signup().client
    expect(client.post("/api/v1/stocks/buy", json={"stock_type": "high_vol", "amount": 1_000_000}), 201)

    expect(client.post(TURNS, json=SAVE), 201)

    assert client.get("/api/v1/stocks").json()["holdings"][0]["current_value"] != 1_000_000


# ── 대출·신용 ────────────────────────────────────


def test_loan_disbursed_and_repaid_on_schedule(api: E2EApi) -> None:
    client = api.signup(monthly_salary=3_000_000).client
    credit = client.get("/api/v1/credit").json()
    assert (credit["score"], credit["grade"]) == (50, "C")
    assert client.get("/api/v1/loans/eligibility").status_code == 200
    assert client.get("/api/v1/loans/quote", params={"principal": 900_000, "duration_months": 3}).status_code == 200
    over_limit = client.post("/api/v1/loans/apply", json={"principal": 2_000_000, "duration_months": 3})
    assert over_limit.json()["code"] == "LOAN_LIMIT_EXCEEDED"

    loan = expect(client.post("/api/v1/loans/apply", json={"principal": 900_000, "duration_months": 3}), 201)

    assert client.get("/api/v1/simulation").json()["cash_balance"] == 3_000_000 + 900_000
    assert client.post("/api/v1/loans/apply", json={"principal": 100_000, "duration_months": 3}).status_code == 409
    assert len(client.get(f"/api/v1/loans/{loan['id']}/schedule").json()) == 3

    # 회차는 신청 턴 + 1부터 도래하므로 신청 턴을 포함해 4턴을 진행해야 3회차까지 상환된다
    for _ in range(4):
        expect(client.post(TURNS, json=NORMAL), 201)

    repaid = client.get(f"/api/v1/loans/{loan['id']}").json()
    assert (repaid["status"], repaid["remaining_balance"]) == ("completed", 0)
    assert client.get("/api/v1/credit").json()["score"] == 50 + 1 * 3 + 3
    reasons = [entry["reason"] for entry in client.get("/api/v1/credit/history").json()]
    assert sorted(reasons) == ["loan_complete", "loan_payment", "loan_payment", "loan_payment"]


def test_overdue_when_cash_is_short_on_due_turn(api: E2EApi) -> None:
    # 월급 100만 - 고정 85만 - 변동(save) 15만 = 매달 순현금 0 → 남은 현금 10만으로는 회차(약 30만)를 못 갚는다
    client = api.signup(monthly_salary=1_000_000).client
    expect(client.post(FIXED_EXPENSES, json={"name": "월세", "amount": 850_000}), 201)
    expect(client.post("/api/v1/loans/apply", json={"principal": 900_000, "duration_months": 3}), 201)
    cash = client.get("/api/v1/simulation").json()["cash_balance"]
    expect(client.post("/api/v1/stocks/buy", json={"stock_type": "index", "amount": cash - 100_000}), 201)

    first, second = (expect(client.post(TURNS, json=SAVE), 201) for _ in range(2))

    assert (first["is_overdue"], second["is_overdue"]) == (False, True)
    assert client.get("/api/v1/credit").json()["score"] == 50 - 4
    assert [entry["reason"] for entry in client.get("/api/v1/credit/history").json()] == ["overdue"]


# ── 소유권 ──────────────────────────────────────


def test_other_users_resources_are_hidden(api: E2EApi) -> None:
    owner = api.signup().client
    other = api.signup().client
    fixed_expense = expect(owner.post(FIXED_EXPENSES, json={"name": "월세", "amount": 600_000}), 201)
    loan = expect(owner.post("/api/v1/loans/apply", json={"principal": 500_000, "duration_months": 3}), 201)

    assert other.get(f"/api/v1/loans/{loan['id']}").status_code == 404
    assert other.get(f"/api/v1/loans/{loan['id']}/schedule").status_code == 404
    assert other.patch(f"{FIXED_EXPENSES}/{fixed_expense['id']}", json={"amount": 1}).status_code == 404
    assert other.delete(f"{FIXED_EXPENSES}/{fixed_expense['id']}").status_code == 404
