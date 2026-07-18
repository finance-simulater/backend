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

# status -> code 기본값. api/domains/errors.md "공통" 표와 맞춘다.
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
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "detail": exc.detail})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = _DEFAULT_CODE_BY_STATUS.get(exc.status_code, "INTERNAL_ERROR")
    return JSONResponse(status_code=exc.status_code, content={"code": code, "detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"code": "INVALID_REQUEST", "detail": str(exc)})
