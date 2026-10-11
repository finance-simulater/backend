"""openapi.yaml ↔ 실제 API 응답 계약 테스트 공용 유틸 (finance-simulater/backend#40).

`spec/api/openapi.yaml`이 API 명세의 SSOT다(spec/docs/CONVENTIONS.md). 기댓값을 테스트에
손으로 적는 대신 스펙 파일에서 직접 읽어 실제 응답과 대조해, 둘 중 한쪽만 바뀌면 깨지게 한다.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

# tests/contract/conftest.py → backend/ → backend/spec/api/openapi.yaml
SPEC_PATH = Path(__file__).resolve().parents[2] / "spec" / "api" / "openapi.yaml"

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})

SpecDict = dict[str, Any]


def _openapi_to_json_schema(node: Any) -> Any:
    """OpenAPI 3.0 고유 키워드를 jsonschema가 이해하는 형태로 변환한다.

    jsonschema는 `nullable: true`(JSON Schema엔 없는 OpenAPI 3.0 전용 키워드)를 모르기 때문에
    그대로 두면 null 값이 type 위반으로 잡힌다. 스키마 전체를 `anyOf: [원래 스키마, null]`로 감싸
    `type`·`$ref`·`allOf`(OpenAPI 3.0에서 $ref에 nullable을 붙이는 방식)·`enum` 어느 형태든
    null을 허용한다 — `type`만 `[type, "null"]`로 바꾸면 `enum`·`allOf`가 여전히 null을 거부한다.
    """
    if isinstance(node, list):
        return [_openapi_to_json_schema(item) for item in node]
    if not isinstance(node, dict):
        return node

    converted = {key: _openapi_to_json_schema(value) for key, value in node.items() if key != "nullable"}
    if node.get("nullable"):
        return {"anyOf": [converted, {"type": "null"}]}
    return converted


@pytest.fixture(scope="session")
def openapi_spec() -> SpecDict:
    """openapi.yaml을 로드해 jsonschema로 검증 가능한 형태로 돌려준다.

    spec은 서브모듈이라 `git submodule update --init spec` 전에는 파일이 없다. 그런 로컬
    환경에서 계약 테스트만 빨간불이 되는 걸 막기 위해 skip한다 — CI는 submodules: true로
    체크아웃하므로(.github/workflows/test.yml) 드리프트는 CI에서 반드시 잡힌다.
    """
    if not SPEC_PATH.exists():
        pytest.skip(f"openapi.yaml 없음: {SPEC_PATH} — `git submodule update --init spec` 필요")
    return _openapi_to_json_schema(yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8")))


def spec_operations(spec: SpecDict) -> list[tuple[str, str, SpecDict]]:
    """스펙에 정의된 (path, method, operation) 전체 목록."""
    return [
        (path, method, operation)
        for path, path_item in spec["paths"].items()
        for method, operation in path_item.items()
        if method in HTTP_METHODS
    ]


def find_operation(spec: SpecDict, path: str, method: str) -> SpecDict:
    path_item = spec["paths"].get(path)
    assert path_item is not None, f"openapi.yaml에 {path} 경로가 없다"
    operation = path_item.get(method)
    assert operation is not None, f"openapi.yaml에 {method.upper()} {path} operation이 없다"
    return operation


def _format_errors(errors: list[Any]) -> str:
    return "\n".join(f"  - $.{'.'.join(str(part) for part in error.absolute_path)}: {error.message}" for error in errors)


def assert_response_matches_spec(spec: SpecDict, response: Any, path: str, method: str) -> None:
    """실제 HTTP 응답이 openapi.yaml의 해당 operation 정의와 일치하는지 검증한다.

    - 응답한 status code가 스펙에 정의돼 있는지
    - 응답 body가 그 status code의 application/json 스키마를 만족하는지
    """
    operation = find_operation(spec, path, method)
    status_code = str(response.status_code)
    responses = operation["responses"]

    assert status_code in responses, (
        f"{method.upper()} {path}: 실제 응답 {status_code}가 openapi.yaml에 정의되지 않음 "
        f"(정의된 응답: {sorted(responses)})"
    )

    content = responses[status_code].get("content")
    if content is None:  # 본문 없는 응답(204 등)은 스펙에 content가 없다
        return

    schema = content["application/json"]["schema"]
    # `#/components/...` $ref가 풀리도록 스펙 루트의 components를 스키마 문서에 함께 붙인다.
    validator = Draft202012Validator({**schema, "components": spec["components"]}, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(response.json()), key=lambda error: list(error.absolute_path))

    assert not errors, f"{method.upper()} {path} {status_code} 응답이 openapi.yaml 스키마와 불일치:\n{_format_errors(errors)}"
