from sqlalchemy.orm import Session

from app.api.v1.stock.repository import StockRepository
from app.api.v1.stock.schema import STOCK_META, StockBuyRequest, StockSellRequest
from app.api.v1.simulation.model import SimulationState
from app.api.v1.stock.model import StockHolding
from app.core.exceptions import bad_request, not_found


def _to_holding_dict(holding: StockHolding) -> dict:
    """StockHolding 모델 → StockHoldingItem 스키마용 dict"""
    meta = STOCK_META[holding.stock_type]
    profit_loss = holding.current_value - holding.principal
    profit_loss_rate = (
        round(profit_loss / holding.principal * 100, 1) if holding.principal else 0.0
    )
    return {
        "id": holding.id,
        "stock_type": holding.stock_type,
        "name": meta["name"],
        "risk_level": meta["risk"],
        "volatility_range": meta["range"],
        "principal": holding.principal,
        "current_value": holding.current_value,
        "profit_loss": profit_loss,
        "profit_loss_rate": profit_loss_rate,
    }


class StockService:
    def __init__(self, db: Session, repository: StockRepository | None = None) -> None:
        self.db = db
        self.repository = repository or StockRepository(db)

    def get_portfolio(self, user_id: int) -> dict:
        state = self._get_state_or_404(user_id)
        holdings = self.repository.find_all_by_user(user_id)

        total_principal = sum(h.principal for h in holdings)
        total_current_value = sum(h.current_value for h in holdings)

        return {
            "cash_balance": state.cash_balance,
            "total_principal": total_principal,
            "total_current_value": total_current_value,
            "total_profit_loss": total_current_value - total_principal,
            "holdings": [_to_holding_dict(h) for h in holdings],
        }

    # ── 매수 ──────────────────────────────────────────────────────

    def buy(self, user_id: int, request: StockBuyRequest) -> dict:
        # 락 순서: SimulationState → StockHolding (매수/매도 공통) 로 통일해 데드락 방지.
        state = self._get_state_or_404(user_id, for_update=True)

        if request.amount > state.cash_balance:
            raise bad_request(
                f"잔액이 부족합니다. 보유 현금: {state.cash_balance:,}원, 매수 시도: {request.amount:,}원",
                code="INSUFFICIENT_BALANCE",
            )

        holding = self.repository.find_by_user_and_type(
            user_id, request.stock_type, for_update=True
        )
        if holding:
            holding = self.repository.update_holding(
                holding,
                principal=holding.principal + request.amount,
                current_value=holding.current_value + request.amount,
            )
        else:
            holding = self.repository.create(user_id, request.stock_type, request.amount)

        self.repository.update_cash_balance(state, state.cash_balance - request.amount)
        self.db.commit()

        return {
            "holding": _to_holding_dict(holding),
            "cash_balance": state.cash_balance,
            "realized_amount": None,
        }

    # ── 매도 ──────────────────────────────────────────────────────

    def sell(self, user_id: int, request: StockSellRequest) -> dict:
        # 락 순서: SimulationState → StockHolding (매수와 동일) 로 통일해 데드락 방지.
        state = self._get_state_or_404(user_id, for_update=True)

        holding = self.repository.find_by_user_and_type(
            user_id, request.stock_type, for_update=True
        )
        if holding is None:
            raise not_found("보유한 주식이 없습니다.")

        if request.amount > holding.current_value:
            raise bad_request(
                f"매도 금액이 보유 평가금액({holding.current_value:,}원)을 초과합니다.",
                code="INSUFFICIENT_HOLDINGS",
            )

        # 반올림 오차 누적 방지: 매도한 원금분을 계산해 원금에서 차감한다.
        sell_ratio = request.amount / holding.current_value
        sold_principal = round(holding.principal * sell_ratio)
        new_principal = holding.principal - sold_principal
        new_current = holding.current_value - request.amount

        if new_current == 0:
            self.repository.delete_holding(holding)
            self.repository.update_cash_balance(state, state.cash_balance + request.amount)
            self.db.commit()
            return {
                "holding": None,
                "cash_balance": state.cash_balance,
                "realized_amount": request.amount,
            }

        holding = self.repository.update_holding(holding, new_principal, new_current)
        self.repository.update_cash_balance(state, state.cash_balance + request.amount)
        self.db.commit()

        return {
            "holding": _to_holding_dict(holding),
            "cash_balance": state.cash_balance,
            "realized_amount": request.amount,
        }

    # ── 내부 헬퍼 ──────────────────────────────────────────────────

    def _get_state_or_404(self, user_id: int, for_update: bool = False) -> SimulationState:
        state = self.repository.find_simulation_state(user_id, for_update=for_update)
        if state is None:
            raise not_found("시뮬레이션 상태를 찾을 수 없습니다. 온보딩을 완료해주세요.")
        return state
