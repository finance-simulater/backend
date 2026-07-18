from pydantic import BaseModel, ConfigDict

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
