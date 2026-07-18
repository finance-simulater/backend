from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1 import models  # noqa: F401
from app.api.v1.auth.router import router as auth_router
from app.api.v1.loan.router import router as loan_router
from app.api.v1.user.router import router as user_router
from app.core.exceptions import AppHTTPException
from app.health.router import router as health_router

app = FastAPI()

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(loan_router)

# FastAPI 기본 HTTPException엔 `code`가 없다. AppHTTPException을 못 쓴 곳(또는 아직 안 고친 곳)에서도
# 응답 형식이 깨지지 않도록, status 코드만 보고 채워 넣을 기본값. api/domains/errors.md "공통" 표와 맞춘다.
_DEFAULT_CODE_BY_STATUS = {
    400: "INVALID_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "INVALID_REQUEST",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}

@app.exception_handler(AppHTTPException)
async def app_http_exception_handler(request: Request, exc: AppHTTPException) -> JSONResponse:
    # not_found()/service_unavailable() 등 우리가 직접 만든 헬퍼로 raise한 경우. exc.code를 그대로 쓴다.
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "detail": exc.detail})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # 안전망: 누군가 AppHTTPException 대신 기본 HTTPException(status_code=..., detail=...)을 raise해도
    # code 없는 응답이 나가지 않도록 status 기준으로 기본 code를 채운다.
    code = _DEFAULT_CODE_BY_STATUS.get(exc.status_code, "INTERNAL_ERROR")
    return JSONResponse(status_code=exc.status_code, content={"code": code, "detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # 요청 body/쿼리가 스키마 검증(Pydantic)에서 실패했을 때 FastAPI가 자동으로 던지는 예외를 잡는다.
    return JSONResponse(status_code=422, content={"code": "INVALID_REQUEST", "detail": str(exc)})
