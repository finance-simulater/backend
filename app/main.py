from fastapi import FastAPI

from app.api.v1 import models  # noqa: F401
from app.api.v1.auth.router import router as auth_router
from app.api.v1.loan.router import router as loan_router
from app.api.v1.user.router import router as user_router
from app.health.router import router as health_router

app = FastAPI()

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(loan_router)
