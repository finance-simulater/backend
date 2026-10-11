"""계약 테스트 공용 유틸(conftest.py) 자체의 경계 케이스 검증 (#40)."""

from pathlib import Path

import pytest

from tests.contract import conftest
from tests.contract.conftest import _openapi_to_json_schema

pytestmark = pytest.mark.contract


def test_nullable_keyword_wraps_schema_with_null() -> None:
    converted = _openapi_to_json_schema({"type": "integer", "nullable": True})

    assert converted == {"anyOf": [{"type": "integer"}, {"type": "null"}]}


def test_property_named_nullable_is_not_treated_as_keyword() -> None:
    schema = {"type": "object", "properties": {"nullable": {"type": "boolean"}}}

    assert _openapi_to_json_schema(schema) == schema


def test_missing_spec_fails_in_ci(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(conftest, "SPEC_PATH", tmp_path / "missing.yaml")
    monkeypatch.setenv("CI", "true")

    with pytest.raises(pytest.fail.Exception):
        conftest.openapi_spec.__wrapped__()


def test_missing_spec_skips_locally(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(conftest, "SPEC_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("CI", raising=False)

    with pytest.raises(pytest.skip.Exception):
        conftest.openapi_spec.__wrapped__()
