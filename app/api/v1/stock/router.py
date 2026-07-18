from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.stock.schema import StockPortfolioResponse
from app.api.v1.stock.service import StockService
from app.database import get_db

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


def get_stock_service(db: Session = Depends(get_db)) -> StockService:
    return StockService(db)


@router.get("", response_model=StockPortfolioResponse)
async def get_portfolio(
    user_id: int,
    service: StockService = Depends(get_stock_service),
):
    """투자탭 메인: 보유 주식 현황 + 투자 가능 현금 조회"""
    return service.get_portfolio(user_id)


# TODO: POST /buy   → 매수
# TODO: POST /sell  → 매도
