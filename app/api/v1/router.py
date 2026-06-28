from fastapi import APIRouter
from app.api.v1.endpoints import user, loan

router = APIRouter()

router.include_router(user.router, prefix="/users", tags=["users"])
router.include_router(loan.router, prefix="/loans", tags=["loans"])
