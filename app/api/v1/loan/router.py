from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.loan.schema import (
    LoanApplicationRequest,
    LoanEligibilityResponse,
    LoanQuoteResponse,
    LoanResponse,
    LoanStatusResponse,
    RepaymentScheduleItem,
)
from app.api.v1.loan.service import LoanService
from app.api.v1.user.model import User
from app.database import get_db

router = APIRouter(prefix="/api/v1/loans", tags=["loans"])


def get_loan_service(db: Session = Depends(get_db)) -> LoanService:
    return LoanService(db)


@router.get("/", response_model=list[LoanResponse])
async def list_loans(service: LoanService = Depends(get_loan_service)):
    return service.get_loans()


# /{loan_id} 패턴과 겹치지 않도록 정적 경로들을 먼저 등록한다.
@router.get("/eligibility", response_model=LoanEligibilityResponse)
async def get_eligibility(
    current_user: User = Depends(get_current_user),
    service: LoanService = Depends(get_loan_service),
):
    return service.get_eligibility(current_user.id)


@router.get("/quote", response_model=LoanQuoteResponse)
async def get_quote(
    principal: int = Query(gt=0),
    duration_months: Literal[3, 6, 12] = Query(...),
    current_user: User = Depends(get_current_user),
    service: LoanService = Depends(get_loan_service),
):
    return service.get_quote(current_user.id, principal, duration_months)


@router.get("/active", response_model=LoanStatusResponse)
async def get_active_loan(
    current_user: User = Depends(get_current_user),
    service: LoanService = Depends(get_loan_service),
):
    return service.get_active_loan_status(current_user.id)


@router.post(
    "/apply",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def apply_for_loan(
    application: LoanApplicationRequest,
    current_user: User = Depends(get_current_user),
    service: LoanService = Depends(get_loan_service),
):
    return service.apply_for_loan(current_user.id, application.principal, application.duration_months)


@router.get("/{loan_id}", response_model=LoanResponse)
async def get_loan(loan_id: int, service: LoanService = Depends(get_loan_service)):
    return service.get_loan(loan_id)


@router.get("/{loan_id}/schedule", response_model=list[RepaymentScheduleItem])
async def get_loan_schedule(loan_id: int, service: LoanService = Depends(get_loan_service)):
    return service.get_schedule(loan_id)
