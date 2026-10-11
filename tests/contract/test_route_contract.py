"""openapi.yaml에 정의된 경로/메서드와 실제 FastAPI 라우트가 일치하는지 검증 (#40).

- 스펙 → 앱: 스펙에 있는 엔드포인트는 앱에 구현돼 있어야 한다.
- 앱 → 스펙: 앱에 있는데 스펙에 없는 엔드포인트는 UNDOCUMENTED_ROUTES(허용 목록)에 있어야 한다.
  auth/loans/stocks는 openapi.yaml에 아직 의도적으로 미문서화 상태라 허용 목록으로 예외 처리하고,
  그 밖의 신규 라우트가 스펙 없이 추가되면 실패시킨다. 허용 목록을 비우는 작업은
  finance-simulater/spec#9에서 진행한다.
"""

import pytest

from app.main import app
from tests.contract.conftest import HTTP_METHODS, SpecDict, spec_operations

pytestmark = pytest.mark.contract

# openapi.yaml에 아직 경로가 없는 엔드포인트 (= 스펙 문서화 부채).
# 스펙에 경로가 추가되면 test_undocumented_routes_are_not_stale이 실패하므로 여기서 지운다.
UNDOCUMENTED_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        # auth
        ("/api/v1/auth/signup", "post"),
        ("/api/v1/auth/email/send", "post"),
        ("/api/v1/auth/email/verify", "post"),
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/refresh", "post"),
        ("/api/v1/auth/logout", "post"),
        ("/api/v1/auth/me", "get"),
        # loans
        ("/api/v1/loans/", "get"),
        ("/api/v1/loans/eligibility", "get"),
        ("/api/v1/loans/quote", "get"),
        ("/api/v1/loans/active", "get"),
        ("/api/v1/loans/apply", "post"),
        ("/api/v1/loans/{loan_id}", "get"),
        ("/api/v1/loans/{loan_id}/schedule", "get"),
        # stocks
        ("/api/v1/stocks", "get"),
        ("/api/v1/stocks/buy", "post"),
        ("/api/v1/stocks/sell", "post"),
    }
)


def _app_routes() -> set[tuple[str, str]]:
    """앱이 실제로 노출하는 (path, method) 집합.

    app.routes를 직접 읽지 않는 이유: include_router가 지연 적용돼(FastAPI 0.138의
    _IncludedRouter) 요청 전에는 APIRoute가 펼쳐지지 않는다. app.openapi()는 등록된
    라우트에서 생성되므로 내부 구조에 의존하지 않고 같은 정보를 얻을 수 있다.
    /docs·/redoc·/openapi.json은 include_in_schema=False라 여기에 포함되지 않는다.
    """
    return {
        (path, method)
        for path, path_item in app.openapi()["paths"].items()
        for method in path_item
        if method in HTTP_METHODS
    }


def _spec_routes(spec: SpecDict) -> set[tuple[str, str]]:
    return {(path, method) for path, method, _ in spec_operations(spec)}


def _format_routes(routes: set[tuple[str, str]]) -> list[str]:
    return sorted(f"{method.upper()} {path}" for path, method in routes)


def test_every_spec_endpoint_exists_in_app(openapi_spec: SpecDict) -> None:
    missing = _spec_routes(openapi_spec) - _app_routes()

    assert not missing, f"openapi.yaml에 있으나 앱에 구현되지 않은 엔드포인트: {_format_routes(missing)}"


def test_every_app_endpoint_is_documented_or_allowlisted(openapi_spec: SpecDict) -> None:
    undocumented = _app_routes() - _spec_routes(openapi_spec) - UNDOCUMENTED_ROUTES

    assert not undocumented, (
        f"앱에 있으나 openapi.yaml에 없는 엔드포인트: {_format_routes(undocumented)} "
        "— spec 레포에 경로를 추가하거나, 의도적으로 미문서화라면 UNDOCUMENTED_ROUTES에 등록할 것"
    )


def test_undocumented_routes_are_not_stale(openapi_spec: SpecDict) -> None:
    now_documented = UNDOCUMENTED_ROUTES & _spec_routes(openapi_spec)

    assert not now_documented, (
        f"openapi.yaml에 문서화됐으므로 UNDOCUMENTED_ROUTES에서 제거할 것: {_format_routes(now_documented)}"
    )


def test_undocumented_routes_exist_in_app() -> None:
    removed = UNDOCUMENTED_ROUTES - _app_routes()

    assert not removed, f"앱에서 삭제됐으므로 UNDOCUMENTED_ROUTES에서 제거할 것: {_format_routes(removed)}"
