from sqlalchemy.orm import Session

from app.api.v1.stock.repository import StockRepository
from app.api.v1.stock.schema import STOCK_META
from app.api.v1.simulation.model import SimulationState
from app.api.v1.stock.model import StockHolding
from app.core.exceptions import not_found


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

    def _get_state_or_404(self, user_id: int) -> SimulationState:
        state = self.repository.find_simulation_state(user_id)
        if state is None:
            raise not_found("시뮬레이션 상태를 찾을 수 없습니다. 온보딩을 완료해주세요.")
        return state
