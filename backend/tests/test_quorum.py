import pytest

from zheka.core.ids import FlatId
from zheka.core.services.quorum import FlatArea, forecast


def _flat(flat_id: int, area: int | None) -> FlatArea:
    return FlatArea(flat_id=FlatId(flat_id), area=area)


def test_a_flat_counted_twice_in_voted_counts_once_in_area() -> None:
    all_flats = [_flat(1, 5000), _flat(2, 3000), _flat(3, 2000)]
    voted = [_flat(1, 5000), _flat(1, 5000)]

    result = forecast(voted, all_flats, unverified_votes=4)

    assert result.voted_flats == 1
    assert result.total_flats == 3
    assert result.voted_area == 5000
    assert result.unweighted_votes == 4


@pytest.mark.parametrize(
    ("voted_area", "expected_reached"),
    [
        (4999, False),
        (5000, True),
        (5001, True),
    ],
)
def test_area_percent_crossing_50_flips_quorum_reached(
    voted_area: int,
    expected_reached: bool,
) -> None:
    all_flats = [_flat(1, 10_000)]
    voted = [_flat(1, voted_area)]

    result = forecast(voted, all_flats, unverified_votes=0)

    assert result.quorum_reached is expected_reached


def test_flats_with_a_null_area_are_excluded_from_both_sums() -> None:
    all_flats = [_flat(1, 5000), _flat(2, None)]
    voted = [_flat(1, 5000), _flat(2, None)]

    result = forecast(voted, all_flats, unverified_votes=0)

    # квартира без площади остается в счете квартир, но не в площадях
    assert result.total_area == 5000
    assert result.voted_area == 5000
    assert result.voted_flats == 2
    assert result.total_flats == 2
    assert result.area_percent == 10_000


def test_total_area_zero_gives_zero_percent_and_no_quorum() -> None:
    all_flats = [_flat(1, None), _flat(2, None)]

    result = forecast([], all_flats, unverified_votes=0)

    assert result.total_area == 0
    assert result.area_percent == 0
    assert result.quorum_reached is False
