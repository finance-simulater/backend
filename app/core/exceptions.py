from fastapi import HTTPException, status


class AppHTTPException(HTTPException):
    """HTTPException that carries a machine-readable `code` (api/domains/errors.md)."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code

def not_found(detail: str, code: str = "NOT_FOUND") -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_404_NOT_FOUND, code=code, detail=detail)


def conflict(detail: str, code: str) -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_409_CONFLICT, code=code, detail=detail)

def unprocessable(detail: str, code: str) -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, code=code, detail=detail)

def service_unavailable(detail: str, code: str = "SERVICE_UNAVAILABLE") -> AppHTTPException:
    return AppHTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, code=code, detail=detail)
