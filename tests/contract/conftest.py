"""openapi.yaml ↔ 실제 API 응답 계약 테스트 공용 유틸 (finance-simulater/backend#40).

`spec/api/openapi.yaml`이 API 명세의 SSOT다(spec/docs/CONVENTIONS.md). 기댓값을 테스트에
손으로 적는 대신 스펙 파일에서 직접 읽어 실제 응답과 대조해, 둘 중 한쪽만 바뀌면 깨지게 한다.
"""

import os
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

    `nullable` 키는 값이 bool일 때만 키워드로 본다. `properties`·`components.schemas` 같은 이름 맵에
    `nullable`이라는 이름의 필드/스키마가 있으면 값이 dict라서 키워드와 구분된다.
    """
    if isinstance(node, list):
        return [_openapi_to_json_schema(item) for item in node]
    if not isinstance(node, dict):
        return node

    is_nullable = node.get("nullable") is True
    converted = {
        key: _openapi_to_json_schema(value)
        for key, value in node.items()
        if not (key == "nullable" and isinstance(value, bool))
    }
    if is_nullable:
        return {"anyOf": [converted, {"type": "null"}]}
    return converted


def load_openapi_spec(path: Path = SPEC_PATH) -> SpecDict:
    """openapi.yaml을 로드해 jsonschema로 검증 가능한 형태로 돌려준다.

    fixture와 분리한 이유: skip/fail 분기를 테스트에서 일반 함수로 직접 호출해 검증하기 위함
    (fixture 함수를 직접 부르려면 pytest 내부 구현인 `__wrapped__`에 기대야 한다).

    spec은 서브모듈이라 `git submodule update --init spec` 전에는 파일이 없다. 그런 로컬
    환경에서 계약 테스트만 빨간불이 되는 걸 막기 위해 skip한다.
    CI(`CI` 환경변수, GitHub Actions가 자동 설정)에서는 skip 대신 실패시킨다 — CI는 서브모듈 포인터
    커밋을 deploy key로 직접 checkout하는데(.github/workflows/test.yml), 키 누락·checkout 경로 변경
    등으로 파일이 없으면 계약 테스트 전체가 skip된 채 초록불이 돼 드리프트를 조용히 놓치기 때문.
    """
    if not path.exists():
        message = f"openapi.yaml 없음: {path} — `git submodule update --init spec` 필요"
        if os.environ.get("CI"):
            pytest.fail(f"{message} (CI에서는 spec checkout이 필수)")
        pytest.skip(message)
    return _openapi_to_json_schema(yaml.safe_load(path.read_text(encoding="utf-8")))


@pytest.fixture(scope="session")
def openapi_spec() -> SpecDict:
    return load_openapi_spec()


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


def _json_path(error: Any) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return f"$.{path}" if path else "$"


def _format_errors(errors: list[Any]) -> str:
    return "\n".join(f"  - {_json_path(error)}: {error.message}" for error in errors)


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

    assert "application/json" in content, (
        f"{method.upper()} {path} {status_code}: 스펙의 응답 content에 application/json이 없음 "
        f"(정의된 타입: {sorted(content)}) — 이 헬퍼는 JSON 응답만 검증한다"
    )
    schema = content["application/json"]["schema"]
    # `#/components/...` $ref가 풀리도록 스펙 루트의 components를 스키마 문서에 함께 붙인다.
    # 같은 문서 내부 참조만 지원한다 — 스펙이 외부 파일 $ref(`./schemas/x.yaml`)를 쓰기 시작하면
    # referencing Registry로 파일을 등록하는 방식으로 바꿔야 한다.
    # FormatChecker의 `date-time`은 rfc3339-validator가 설치돼 있지 않아 실제로는 검증되지 않는다(#43).
    validator = Draft202012Validator({**schema, "components": spec["components"]}, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(response.json()), key=lambda error: list(error.absolute_path))

    assert not errors, f"{method.upper()} {path} {status_code} 응답이 openapi.yaml 스키마와 불일치:\n{_format_errors(errors)}"
