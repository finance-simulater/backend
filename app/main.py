from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import models  # noqa: F401
from app.api.v1.auth.router import router as auth_router
from app.api.v1.loan.router import router as loan_router
from app.api.v1.simulation.router import router as simulation_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.health.router import router as health_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(loan_router)
app.include_router(simulation_router)

register_exception_handlers(app)
