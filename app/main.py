from fastapi import FastAPI
from app.api.v1.router import router

app = FastAPI()

# 모든 v1 엔드포인트는 /api/v1 하위에 등록됨
app.include_router(router, prefix="/api/v1")
