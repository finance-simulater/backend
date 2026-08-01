from fastapi import HTTPException, status


class AppHTTPException(HTTPException):
    """HTTPException that carries a machine-readable `code` (api/domains/errors.md)."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code

def not_found(detail: str, code: str = "NOT_FOUND") -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_404_NOT_FOUND, code=code, detail=detail)


def bad_request(detail: str, code: str = "INVALID_REQUEST") -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_400_BAD_REQUEST, code=code, detail=detail)


def conflict(detail: str, code: str) -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_409_CONFLICT, code=code, detail=detail)


def forbidden(detail: str, code: str = "FORBIDDEN") -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_403_FORBIDDEN, code=code, detail=detail)


def unauthorized(detail: str, code: str = "UNAUTHENTICATED") -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_401_UNAUTHORIZED, code=code, detail=detail)


def too_many_requests(detail: str, code: str = "TOO_MANY_REQUESTS") -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, code=code, detail=detail)


def unprocessable(detail: str, code: str) -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, code=code, detail=detail)

def service_unavailable(detail: str, code: str = "SERVICE_UNAVAILABLE") -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, code=code, detail=detail)
