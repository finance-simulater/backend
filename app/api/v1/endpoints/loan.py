from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_loans():
    return []


@router.get("/{loan_id}")
async def get_loan(loan_id: int):
    return {"loan_id": loan_id}
