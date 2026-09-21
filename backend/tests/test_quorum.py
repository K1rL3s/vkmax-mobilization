import pytest

from zheka.core.services.quorum import forecast


@pytest.mark.parametrize(
    ("voted_area", "expected_reached"), [(4999, False), (5000, True), (5001, True)]
)
def test_area_percent_crossing_50_flips_quorum_reached(
    voted_area: int, expected_reached: bool
) -> None:
    result = forecast([voted_area], [10_000], unverified_votes=0)

    assert result.quorum_reached is expected_reached


def test_flats_with_a_null_area_are_excluded_from_both_sums() -> None:
    result = forecast([5000, None], [5000, None], unverified_votes=0)

    # квартира без площади остается в счете квартир, но не в площадях
    assert result.total_area == 5000
    assert result.voted_area == 5000
    assert result.voted_flats == 2
    assert result.total_flats == 2
    assert result.area_percent == 10_000


def test_total_area_zero_gives_zero_percent_and_no_quorum() -> None:
    result = forecast([], [None, None], unverified_votes=0)

    assert result.total_area == 0
    assert result.area_percent == 0
    assert result.quorum_reached is False
    assert (result.voted_flats, result.total_flats) == (0, 2)
