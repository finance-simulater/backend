"""openapi.yaml에 정의된 경로/메서드가 실제 FastAPI 라우트로 존재하는지 검증 (#40).

반대 방향(앱에 있는데 스펙에 없음)은 검사하지 않는다 — auth/loan/stock은 openapi.yaml에
아직 의도적으로 미문서화 상태(주석)다.
"""

from app.main import app
from tests.contract.conftest import HTTP_METHODS, SpecDict, spec_operations


def _app_routes() -> set[tuple[str, str]]:
    """앱이 실제로 노출하는 (path, method) 집합.

    app.routes를 직접 읽지 않는 이유: include_router가 지연 적용돼(FastAPI 0.138의
    _IncludedRouter) 요청 전에는 APIRoute가 펼쳐지지 않는다. app.openapi()는 등록된
    라우트에서 생성되므로 내부 구조에 의존하지 않고 같은 정보를 얻을 수 있다.
    """
    return {
        (path, method)
        for path, path_item in app.openapi()["paths"].items()
        for method in path_item
        if method in HTTP_METHODS
    }


def test_every_spec_endpoint_exists_in_app(openapi_spec: SpecDict) -> None:
    app_routes = _app_routes()

    missing = [
        f"{method.upper()} {path}"
        for path, method, _ in spec_operations(openapi_spec)
        if (path, method) not in app_routes
    ]

    assert not missing, f"openapi.yaml에 있으나 앱에 구현되지 않은 엔드포인트: {missing}"
