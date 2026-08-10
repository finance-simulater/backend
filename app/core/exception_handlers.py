import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppHTTPException

logger = logging.getLogger(__name__)

# FastAPI 기본 HTTPException엔 `code`가 없다. AppHTTPException을 못 쓴 곳(또는 아직 안 고친 곳)에서도
# 응답 형식이 깨지지 않도록, status 코드만 보고 채워 넣을 기본값.
# spec 저장소(finance-simulater/spec)의 api/domains/errors.md "공통" 표와 맞춘다.
_DEFAULT_CODE_BY_STATUS = {
    400: "INVALID_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    429: "TOO_MANY_REQUESTS",
    422: "INVALID_REQUEST",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


async def app_http_exception_handler(request: Request, exc: AppHTTPException) -> JSONResponse:
    # not_found()/service_unavailable() 등 우리가 직접 만든 헬퍼로 raise한 경우. exc.code를 그대로 쓴다.
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "detail": exc.detail})


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # 안전망: 누군가 AppHTTPException 대신 기본 HTTPException(status_code=..., detail=...)을 raise해도
    # code 없는 응답이 나가지 않도록 status 기준으로 기본 code를 채운다.
    code = _DEFAULT_CODE_BY_STATUS.get(exc.status_code, "INTERNAL_ERROR")
    return JSONResponse(status_code=exc.status_code, content={"code": code, "detail": exc.detail})


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # 요청 body/쿼리가 스키마 검증(Pydantic)에서 실패했을 때 FastAPI가 자동으로 던지는 예외를 잡는다.
    return JSONResponse(status_code=422, content={"code": "INVALID_REQUEST", "detail": str(exc)})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 위 세 핸들러가 안 잡는 예상 못한 예외(버그, DB 에러 등). code 없는 기본 500 응답이 나가는 걸 막는다.
    logger.exception("Unhandled exception while processing request: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"code": "INTERNAL_ERROR", "detail": "Internal server error"})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppHTTPException, app_http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
