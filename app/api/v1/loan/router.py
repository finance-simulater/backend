from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.loan.schema import LoanCreate, LoanResponse
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


@router.post("/", response_model=LoanResponse, status_code=status.HTTP_201_CREATED)
async def create_loan(
    loan_create: LoanCreate,
    service: LoanService = Depends(get_loan_service),
):
    return service.create_loan(loan_create)
