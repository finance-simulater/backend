"""계약 테스트 공용 유틸(conftest.py) 자체의 경계 케이스 검증 (#40)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.contract.conftest import _openapi_to_json_schema, assert_response_matches_spec, load_openapi_spec

pytestmark = pytest.mark.contract


def test_nullable_keyword_wraps_schema_with_null() -> None:
    converted = _openapi_to_json_schema({"type": "integer", "nullable": True})

    assert converted == {"anyOf": [{"type": "integer"}, {"type": "null"}]}


def test_property_named_nullable_is_not_treated_as_keyword() -> None:
    schema = {"type": "object", "properties": {"nullable": {"type": "boolean"}}}

    assert _openapi_to_json_schema(schema) == schema


def test_missing_spec_fails_in_ci(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CI", "true")

    with pytest.raises(pytest.fail.Exception):
        load_openapi_spec(tmp_path / "missing.yaml")


def test_missing_spec_skips_locally(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CI", raising=False)

    with pytest.raises(pytest.skip.Exception):
        load_openapi_spec(tmp_path / "missing.yaml")


def test_response_ref_is_resolved_and_body_validated() -> None:
    # 공통 응답 $ref를 풀지 않으면 content가 없어 body 검증이 건너뛰어진다 (#66)
    spec = {
        "paths": {"/x": {"get": {"responses": {"401": {"$ref": "#/components/responses/Unauthenticated"}}}}},
        "components": {
            "responses": {
                "Unauthenticated": {
                    "description": "미인증",
                    "content": {"application/json": {"schema": {"type": "object", "required": ["code"]}}},
                }
            }
        },
    }
    response = SimpleNamespace(status_code=401, json=lambda: {})

    with pytest.raises(AssertionError, match="code"):
        assert_response_matches_spec(spec, response, "/x", "get")


def test_response_ref_to_undefined_component_fails_with_message() -> None:
    spec = {
        "paths": {"/x": {"get": {"responses": {"401": {"$ref": "#/components/responses/Missing"}}}}},
        "components": {"responses": {}},
    }
    response = SimpleNamespace(status_code=401, json=lambda: {})

    with pytest.raises(AssertionError, match="components/responses에 Missing이 없음"):
        assert_response_matches_spec(spec, response, "/x", "get")
