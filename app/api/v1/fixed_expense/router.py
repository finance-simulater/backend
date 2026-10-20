from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.fixed_expense.schema import FixedExpenseCreate, FixedExpenseResponse, FixedExpenseUpdate
from app.api.v1.fixed_expense.service import FixedExpenseService
from app.api.v1.user.model import User
from app.database import get_db

router = APIRouter(prefix="/api/v1/users/me/fixed-expenses", tags=["users"])


def get_fixed_expense_service(db: Session = Depends(get_db)) -> FixedExpenseService:
    return FixedExpenseService(db)


@router.get("", response_model=list[FixedExpenseResponse])
async def list_fixed_expenses(
    current_user: User = Depends(get_current_user),
    service: FixedExpenseService = Depends(get_fixed_expense_service),
):
    return service.get_fixed_expenses(current_user.id)


@router.post("", response_model=FixedExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_fixed_expense(
    request: FixedExpenseCreate,
    current_user: User = Depends(get_current_user),
    service: FixedExpenseService = Depends(get_fixed_expense_service),
):
    return service.create_fixed_expense(current_user.id, request)


@router.patch("/{fixed_expense_id}", response_model=FixedExpenseResponse)
async def update_fixed_expense(
    fixed_expense_id: int,
    request: FixedExpenseUpdate,
    current_user: User = Depends(get_current_user),
    service: FixedExpenseService = Depends(get_fixed_expense_service),
):
    return service.update_fixed_expense(current_user.id, fixed_expense_id, request)


@router.delete("/{fixed_expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fixed_expense(
    fixed_expense_id: int,
    current_user: User = Depends(get_current_user),
    service: FixedExpenseService = Depends(get_fixed_expense_service),
) -> None:
    service.delete_fixed_expense(current_user.id, fixed_expense_id)
