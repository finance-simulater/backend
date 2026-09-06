from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.credit.schema import CreditHistoryEntryResponse, CreditScoreResponse
from app.api.v1.credit.service import CreditService
from app.api.v1.user.model import User
from app.database import get_db

router = APIRouter(prefix="/api/v1/credit", tags=["credit"])


def get_credit_service(db: Session = Depends(get_db)) -> CreditService:
    return CreditService(db)


@router.get("", response_model=CreditScoreResponse)
async def get_credit_score(
    current_user: User = Depends(get_current_user),
    service: CreditService = Depends(get_credit_service),
):
    return service.get_score(current_user.id)


@router.get("/history", response_model=list[CreditHistoryEntryResponse])
async def get_credit_history(
    cursor: int | None = Query(None),
    size: int = Query(20, gt=0, le=100),
    current_user: User = Depends(get_current_user),
    service: CreditService = Depends(get_credit_service),
):
    return service.get_history(current_user.id, cursor, size)
