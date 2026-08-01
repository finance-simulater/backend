from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

# 주식 타입별 UI 표시 정보 (기획서 기준)
STOCK_META = {
    "high_vol": {"name": "고변동성 주식", "risk": "고위험", "range": "-30% ~ +30%"},
    "low_vol":  {"name": "저변동성 주식", "risk": "저위험", "range": "-10% ~ +10%"},
    "index":    {"name": "지수에 투자",   "risk": "중위험", "range": "-5% ~ +5%"},
}


class StockHoldingItem(BaseModel):
    """보유 주식 1종목"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_type: str
    name: str               # "고변동성 주식"
    risk_level: str         # "고위험"
    volatility_range: str   # "-30% ~ +30%"
    principal: int          # 투자 원금
    current_value: int      # 현재 평가금액
    profit_loss: int        # 평가손익 (current_value - principal)
    profit_loss_rate: float # 수익률 %


class StockPortfolioResponse(BaseModel):
    """GET /api/v1/stocks 응답"""
    cash_balance: int           # 투자 가능 현금
    total_principal: int        # 총 투자 원금
    total_current_value: int    # 총 평가금액
    total_profit_loss: int      # 총 평가손익
    holdings: list[StockHoldingItem]


StockType = Literal["high_vol", "low_vol", "index"]


class StockBuyRequest(BaseModel):
    """POST /api/v1/stocks/buy 요청"""
    stock_type: StockType
    amount: int = Field(gt=0, description="매수 금액(원)")


class StockSellRequest(BaseModel):
    """POST /api/v1/stocks/sell 요청. amount = current_value 전액이면 전체 매도"""
    stock_type: StockType
    amount: int = Field(gt=0, description="매도 금액(원)")


class StockActionResponse(BaseModel):
    """매수·매도 공통 응답"""
    holding: StockHoldingItem | None  # 전체 매도 시 None
    cash_balance: int                 # 처리 후 현금 잔액
    realized_amount: int | None = None  # 매도 시 실현 금액 (매수 시 None)
