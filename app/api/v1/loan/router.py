from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.loan.schema import (
    LoanApplicationRequest,
    LoanEligibilityResponse,
    LoanQuoteResponse,
    LoanResponse,
    LoanStatusResponse,
    RepaymentScheduleItem,
)
from app.api.v1.loan.service import LoanService
from app.database import get_db

router = APIRouter(prefix="/api/v1/loans", tags=["loans"])


def get_loan_service(db: Session = Depends(get_db)) -> LoanService:
    return LoanService(db)


@router.get("/", response_model=list[LoanResponse])
async def list_loans(service: LoanService = Depends(get_loan_service)):
    return service.get_loans()


@router.get("/{loan_id}", response_model=LoanResponse)
async def get_loan(loan_id: int, service: LoanService = Depends(get_loan_service)):
    return service.get_loan(loan_id)


@router.get("/{loan_id}/schedule", response_model=list[RepaymentScheduleItem])
async def get_loan_schedule(loan_id: int, service: LoanService = Depends(get_loan_service)):
    return service.get_schedule(loan_id)


@router.get("/users/{user_id}/eligibility", response_model=LoanEligibilityResponse)
async def get_eligibility(user_id: int, service: LoanService = Depends(get_loan_service)):
    return service.get_eligibility(user_id)


@router.get("/users/{user_id}/quote", response_model=LoanQuoteResponse)
async def get_quote(
    user_id: int,
    principal: int = Query(gt=0),
    duration_months: Literal[3, 6, 12] = Query(...),
    service: LoanService = Depends(get_loan_service),
):
    return service.get_quote(user_id, principal, duration_months)


@router.get("/users/{user_id}/active", response_model=LoanStatusResponse)
async def get_active_loan(user_id: int, service: LoanService = Depends(get_loan_service)):
    return service.get_active_loan_status(user_id)


@router.post(
    "/users/{user_id}/apply",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def apply_for_loan(
    user_id: int,
    application: LoanApplicationRequest,
    service: LoanService = Depends(get_loan_service),
):
    return service.apply_for_loan(user_id, application.principal, application.duration_months)
