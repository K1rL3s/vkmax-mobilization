from datetime import date
from typing import Any

import pytest

from zheka.core.charges import (
    ChargeLine,
    breakdown,
    parse_line,
    previous_period,
    to_kopecks,
)
from zheka.core.enums import ServiceType
from zheka.core.errors import InvalidValue


@pytest.mark.parametrize(
    ("product", "is_area", "kopecks"),
    [(149_999, False, 1), (150_000, False, 2), (4_999, True, 0), (5_000, True, 1)],
)
def test_to_kopecks_rounds_half_up(product: int, is_area: bool, kopecks: int) -> None:
    assert to_kopecks(product, is_area=is_area) == kopecks


def test_effects_always_sum_to_the_line_delta_even_where_naive_rounding_breaks_it() -> (
    None
):
    # тариф вырос с 0 до 33_334 (1/10000 руб/ед), объем - с 5 до 7 (1/1000 ед).
    # amount задан как есть, breakdown() его не пересчитывает.
    # Наивный (v_now - v_prev) * t_prev = 0 дал бы tariff_effect(2) + 0 != delta(3)
    previous = ChargeLine(service=ServiceType.COLD_WATER, amount=2, tariff=0, volume=5)
    current = ChargeLine(
        service=ServiceType.COLD_WATER, amount=5, tariff=33_334, volume=7
    )

    line = breakdown([current], [previous]).lines[0]

    assert line.delta == 3
    assert line.tariff_effect == 2
    assert line.volume_effect == 1


@pytest.mark.parametrize(
    ("current", "previous", "kind", "delta"),
    [
        (
            ChargeLine(service=ServiceType.RECALCULATION, amount=1_234),
            None,
            "appeared",
            1_234,
        ),
        (
            None,
            ChargeLine(service=ServiceType.PENALTY, amount=987),
            "disappeared",
            -987,
        ),
        # разовая сумма без тарифа и объема
        (
            ChargeLine(service=ServiceType.MAINTENANCE, amount=1_500),
            ChargeLine(service=ServiceType.MAINTENANCE, amount=1_400),
            "changed",
            100,
        ),
        # тариф есть, объема нет - тоже разовая сумма
        (
            ChargeLine(service=ServiceType.MAINTENANCE, amount=1_500, tariff=100_000),
            ChargeLine(service=ServiceType.MAINTENANCE, amount=1_400, tariff=100_000),
            "changed",
            100,
        ),
    ],
)
def test_a_line_without_a_tariff_effect_puts_the_delta_into_volume(
    current: ChargeLine | None, previous: ChargeLine | None, kind: str, delta: int
) -> None:
    result = breakdown(
        [] if current is None else [current], [] if previous is None else [previous]
    )

    line = result.lines[0]
    assert line.kind == kind
    assert line.delta == delta
    assert line.tariff_effect == 0
    assert line.volume_effect == delta


def test_lines_are_sorted_by_absolute_delta_and_summed() -> None:
    result = breakdown(
        [
            ChargeLine(service=ServiceType.GAS, amount=110),
            ChargeLine(service=ServiceType.ELECTRICITY, amount=5_000),
            ChargeLine(service=ServiceType.HEATING, amount=200),
        ],
        [
            ChargeLine(service=ServiceType.GAS, amount=100),
            ChargeLine(service=ServiceType.HEATING, amount=3_000),
        ],
    )

    assert [line.service for line in result.lines] == [
        ServiceType.ELECTRICITY,
        ServiceType.HEATING,
        ServiceType.GAS,
    ]
    assert result.delta == 10 + 5_000 - 2_800


@pytest.mark.parametrize(
    ("raw", "line"),
    [
        (
            {
                "service": "cold_water",
                "amount": 1_000,
                "volume": 5_000,
                "tariff": 100_000,
                "unit": "m3",
                "note": "по счетчику",
            },
            ChargeLine(
                service=ServiceType.COLD_WATER,
                amount=1_000,
                volume=5_000,
                tariff=100_000,
                unit="m3",
                note="по счетчику",
            ),
        ),
        (
            {"service": "maintenance", "amount": 500},
            ChargeLine(service=ServiceType.MAINTENANCE, amount=500),
        ),
    ],
)
def test_parse_line_reads_the_stored_shape(
    raw: dict[str, Any], line: ChargeLine
) -> None:
    assert parse_line(raw) == line


def test_parse_line_raises_invalid_value_for_an_unknown_service() -> None:
    with pytest.raises(InvalidValue):
        parse_line({"service": "space_heating", "amount": 100})


def test_previous_period_shifts_one_month_back_across_a_year() -> None:
    assert previous_period(date(2026, 3, 1)) == date(2026, 2, 1)
    assert previous_period(date(2026, 1, 1)) == date(2025, 12, 1)
