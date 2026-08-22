from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.stock.schema import (
    StockActionResponse,
    StockBuyRequest,
    StockPortfolioResponse,
    StockSellRequest,
)
from app.api.v1.stock.service import StockService
from app.api.v1.user.model import User
from app.database import get_db

router = APIRouter(prefix="/api/v1/stocks", tags=["investment"])


def get_stock_service(db: Session = Depends(get_db)) -> StockService:
    return StockService(db)


@router.get("", response_model=StockPortfolioResponse)
async def get_portfolio(
    current_user: User = Depends(get_current_user),
    service: StockService = Depends(get_stock_service),
):
    """투자탭 메인: 보유 주식 현황 + 투자 가능 현금 조회"""
    return service.get_portfolio(current_user.id)


@router.post(
    "/buy",
    response_model=StockActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def buy_stock(
    request: StockBuyRequest,
    current_user: User = Depends(get_current_user),
    service: StockService = Depends(get_stock_service),
):
    """주식 매수. 잔액 부족 시 400 INSUFFICIENT_BALANCE"""
    return service.buy(current_user.id, request)


@router.post("/sell", response_model=StockActionResponse)
async def sell_stock(
    request: StockSellRequest,
    current_user: User = Depends(get_current_user),
    service: StockService = Depends(get_stock_service),
):
    """주식 매도(부분·전체). amount = current_value 전액이면 전체 매도"""
    return service.sell(current_user.id, request)
