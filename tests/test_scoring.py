import pytest

from app.core.scoring import clamp_score


@pytest.mark.parametrize("score", [1, 50, 99])
def test_clamp_score_returns_value_within_range(score):
    assert clamp_score(score) == score


@pytest.mark.parametrize("score", [0, 100])
def test_clamp_score_returns_boundary_values_unchanged(score):
    assert clamp_score(score) == score


def test_clamp_score_clamps_below_minimum():
    assert clamp_score(-10) == 0


def test_clamp_score_clamps_above_maximum():
    assert clamp_score(150) == 100


def test_clamp_score_respects_custom_range():
    assert clamp_score(5, minimum=10, maximum=20) == 10
    assert clamp_score(25, minimum=10, maximum=20) == 20
    assert clamp_score(15, minimum=10, maximum=20) == 15


def test_clamp_score_allows_equal_minimum_and_maximum():
    assert clamp_score(50, minimum=30, maximum=30) == 30


def test_clamp_score_raises_when_minimum_greater_than_maximum():
    with pytest.raises(ValueError):
        clamp_score(50, minimum=100, maximum=0)
