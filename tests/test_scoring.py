"""점수 보정 함수 테스트 (finance-simulater/backend#90)."""

import pytest

from app.core.scoring import clamp_score


@pytest.mark.parametrize("score", [1, 50, 99])
def test_score_within_range_is_returned_as_is(score: int) -> None:
    assert clamp_score(score) == score


@pytest.mark.parametrize("score", [0, 100])
def test_boundary_score_is_returned_as_is(score: int) -> None:
    assert clamp_score(score) == score


@pytest.mark.parametrize(("score", "expected"), [(-10, 0), (-1, 0), (101, 100), (150, 100)])
def test_score_out_of_range_is_clamped(score: int, expected: int) -> None:
    assert clamp_score(score) == expected


def test_custom_range_is_applied() -> None:
    assert clamp_score(5, minimum=10, maximum=20) == 10
    assert clamp_score(25, minimum=10, maximum=20) == 20


def test_equal_minimum_and_maximum_returns_that_value() -> None:
    assert clamp_score(70, minimum=50, maximum=50) == 50


def test_minimum_greater_than_maximum_raises() -> None:
    with pytest.raises(ValueError):
        clamp_score(50, minimum=100, maximum=0)
