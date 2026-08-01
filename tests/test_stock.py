"""주식 모의투자 API(GET/buy/sell) 핵심 시나리오 회귀 테스트.

repository를 in-memory Fake로 대체해 서비스 로직을 검증한다.
(DB 연결 없이 정상/에러/삭제/현금 정합성 흐름을 커버)
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.simulation.model import SimulationState
from app.api.v1.stock.model import StockHolding
from app.api.v1.stock.repository import StockRepository
from app.api.v1.stock.router import get_stock_service
from app.api.v1.stock.service import StockService
from app.main import app

USER_ID = 1


class FakeStockRepository:
    """StockRepository를 흉내내는 in-memory 저장소."""

    def __init__(self, cash_balance: int, holdings: list[StockHolding] | None = None) -> None:
        self.state = SimulationState(
            user_id=USER_ID, current_year=2025, current_month=1, cash_balance=cash_balance
        )
        self.holdings: list[StockHolding] = holdings or []
        self._next_id = max((h.id for h in self.holdings), default=0) + 1

    def find_all_by_user(self, user_id: int) -> list[StockHolding]:
        return [h for h in self.holdings if h.user_id == user_id]

    def find_by_user_and_type(
        self, user_id: int, stock_type: str, for_update: bool = False
    ) -> StockHolding | None:
        return next(
            (h for h in self.holdings if h.user_id == user_id and h.stock_type == stock_type),
            None,
        )

    def create(self, user_id: int, stock_type: str, amount: int) -> StockHolding:
        holding = StockHolding(
            id=self._next_id,
            user_id=user_id,
            stock_type=stock_type,
            principal=amount,
            current_value=amount,
        )
        self._next_id += 1
        self.holdings.append(holding)
        return holding

    def update_holding(
        self, holding: StockHolding, principal: int, current_value: int
    ) -> StockHolding:
        holding.principal = principal
        holding.current_value = current_value
        return holding

    def delete_holding(self, holding: StockHolding) -> None:
        self.holdings.remove(holding)

    def find_simulation_state(
        self, user_id: int, for_update: bool = False
    ) -> SimulationState | None:
        return self.state if self.state.user_id == user_id else None

    def update_cash_balance(self, state: SimulationState, new_balance: int) -> None:
        state.cash_balance = new_balance


def make_client(repo: FakeStockRepository) -> TestClient:
    service = StockService(db=MagicMock(), repository=repo)
    app.dependency_overrides[get_stock_service] = lambda: service
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_stock_service, None)


def _holding(stock_type: str, principal: int, current_value: int, hid: int = 1) -> StockHolding:
    return StockHolding(
        id=hid, user_id=USER_ID, stock_type=stock_type, principal=principal, current_value=current_value
    )


# ── 조회 ──────────────────────────────────────────────────────────

def test_get_portfolio_empty() -> None:
    client = make_client(FakeStockRepository(cash_balance=500_000))

    res = client.get(f"/api/v1/stocks/users/{USER_ID}")

    assert res.status_code == 200
    body = res.json()
    assert body["cash_balance"] == 500_000
    assert body["total_principal"] == 0
    assert body["total_current_value"] == 0
    assert body["holdings"] == []


def test_get_portfolio_with_holdings_computes_totals_and_pnl() -> None:
    repo = FakeStockRepository(
        cash_balance=100_000,
        holdings=[_holding("high_vol", principal=200_000, current_value=250_000, hid=1)],
    )
    client = make_client(repo)

    res = client.get(f"/api/v1/stocks/users/{USER_ID}")

    assert res.status_code == 200
    body = res.json()
    assert body["total_principal"] == 200_000
    assert body["total_current_value"] == 250_000
    assert body["total_profit_loss"] == 50_000
    item = body["holdings"][0]
    assert item["name"] == "고변동성 주식"
    assert item["profit_loss"] == 50_000
    assert item["profit_loss_rate"] == 25.0


def test_get_portfolio_no_simulation_state_returns_404() -> None:
    repo = FakeStockRepository(cash_balance=0)
    repo.state.user_id = 999  # 조회 유저와 불일치 → 상태 없음
    client = make_client(repo)

    res = client.get(f"/api/v1/stocks/users/{USER_ID}")

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


# ── 매수 ──────────────────────────────────────────────────────────

def test_buy_success_deducts_cash_and_creates_holding() -> None:
    repo = FakeStockRepository(cash_balance=500_000)
    client = make_client(repo)

    res = client.post(
        f"/api/v1/stocks/users/{USER_ID}/buy",
        json={"stock_type": "high_vol", "amount": 200_000},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["holding"]["principal"] == 200_000
    assert body["cash_balance"] == 300_000
    assert body["realized_amount"] is None
    assert repo.state.cash_balance == 300_000


def test_buy_existing_holding_merges_amount() -> None:
    repo = FakeStockRepository(
        cash_balance=500_000,
        holdings=[_holding("high_vol", principal=200_000, current_value=200_000, hid=1)],
    )
    client = make_client(repo)

    res = client.post(
        f"/api/v1/stocks/users/{USER_ID}/buy",
        json={"stock_type": "high_vol", "amount": 50_000},
    )

    assert res.status_code == 201
    assert res.json()["holding"]["principal"] == 250_000
    assert repo.state.cash_balance == 450_000
    assert len(repo.holdings) == 1  # 새 레코드가 아니라 합산


def test_buy_insufficient_balance_returns_400() -> None:
    repo = FakeStockRepository(cash_balance=150_000)
    client = make_client(repo)

    res = client.post(
        f"/api/v1/stocks/users/{USER_ID}/buy",
        json={"stock_type": "low_vol", "amount": 300_000},
    )

    assert res.status_code == 400
    assert res.json()["code"] == "INSUFFICIENT_BALANCE"
    assert repo.state.cash_balance == 150_000  # 미변경


# ── 매도 ──────────────────────────────────────────────────────────

def test_sell_partial_reduces_principal_and_adds_cash() -> None:
    repo = FakeStockRepository(
        cash_balance=100_000,
        holdings=[_holding("high_vol", principal=200_000, current_value=200_000, hid=1)],
    )
    client = make_client(repo)

    res = client.post(
        f"/api/v1/stocks/users/{USER_ID}/sell",
        json={"stock_type": "high_vol", "amount": 100_000},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["holding"]["principal"] == 100_000  # 절반 매도 → 원금 절반
    assert body["cash_balance"] == 200_000
    assert body["realized_amount"] == 100_000
    assert len(repo.holdings) == 1


def test_sell_full_deletes_holding_and_returns_null() -> None:
    repo = FakeStockRepository(
        cash_balance=100_000,
        holdings=[_holding("index", principal=100_000, current_value=100_000, hid=2)],
    )
    client = make_client(repo)

    res = client.post(
        f"/api/v1/stocks/users/{USER_ID}/sell",
        json={"stock_type": "index", "amount": 100_000},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["holding"] is None
    assert body["cash_balance"] == 200_000
    assert repo.holdings == []  # 레코드 삭제됨


def test_sell_not_owned_returns_404() -> None:
    repo = FakeStockRepository(cash_balance=100_000)
    client = make_client(repo)

    res = client.post(
        f"/api/v1/stocks/users/{USER_ID}/sell",
        json={"stock_type": "low_vol", "amount": 10_000},
    )

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_sell_exceeds_holding_returns_400() -> None:
    repo = FakeStockRepository(
        cash_balance=100_000,
        holdings=[_holding("index", principal=100_000, current_value=100_000, hid=2)],
    )
    client = make_client(repo)

    res = client.post(
        f"/api/v1/stocks/users/{USER_ID}/sell",
        json={"stock_type": "index", "amount": 200_000},
    )

    assert res.status_code == 400
    assert res.json()["code"] == "INSUFFICIENT_HOLDINGS"
    assert repo.state.cash_balance == 100_000  # 미변경
