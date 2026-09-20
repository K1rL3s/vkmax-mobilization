from datetime import date

import pytest

from zheka.core.charges import (
    ChargeLine,
    breakdown,
    parse_line,
    parse_lines,
    previous_period,
    to_kopecks,
)
from zheka.core.enums import ServiceType
from zheka.core.errors import InvalidValue

# ---------------------------------------------------------------------------
# to_kopecks - единственная функция проекта, которая делит деньги
# ---------------------------------------------------------------------------


def test_to_kopecks_rounds_half_up_for_a_volume_line() -> None:
    assert to_kopecks(149_999) == 1  # меньше половины следующего шага - вниз
    assert to_kopecks(150_000) == 2  # ровно половина следующего шага - вверх
    assert to_kopecks(149_000) == 1


def test_to_kopecks_rounds_half_up_for_an_area_line() -> None:
    assert to_kopecks(5_000, is_area=True) == 1  # ровно половина уходит вверх
    assert to_kopecks(4_999, is_area=True) == 0
    assert to_kopecks(15_000, is_area=True) == 2


def test_to_kopecks_of_zero_is_zero() -> None:
    assert to_kopecks(0) == 0
    assert to_kopecks(0, is_area=True) == 0


# ---------------------------------------------------------------------------
# breakdown - разбор дельты по строкам
# ---------------------------------------------------------------------------


def test_effects_always_sum_to_the_line_delta_even_where_naive_rounding_breaks_it() -> (
    None
):
    # тариф вырос с 0 до 33_334 (1/10000 руб/ед), объем - с 5 до 7 (1/1000 ед).
    # amount строк задан произвольно (пришел бы из seed), а не пересчитан
    # здесь - так и работает в проде: breakdown() берет amount как есть
    previous = ChargeLine(service=ServiceType.COLD_WATER, amount=2, tariff=0, volume=5)
    current = ChargeLine(
        service=ServiceType.COLD_WATER, amount=5, tariff=33_334, volume=7
    )

    result = breakdown([current], [previous])

    line = result.lines[0]
    assert line.delta == 3
    assert line.tariff_effect == 2
    assert line.volume_effect == 1
    # тождество - не совпадение частного случая, а прямое следствие того, что
    # volume_effect определен вычитанием, а не независимым произведением:
    # наивный расчет (v_now - v_prev) * t_prev = (7-5)*0 = 0 дал бы
    # tariff_effect(2) + naive(0) = 2 != delta(3)
    assert line.tariff_effect + line.volume_effect == line.delta


def test_tariff_only_change_gives_zero_volume_effect() -> None:
    # объем не меняется (1.000 ед. в обоих периодах), меняется только тариф -
    # числа подобраны так, чтобы деление проходило без остатка
    previous = ChargeLine(
        service=ServiceType.COLD_WATER, amount=1_000, tariff=100_000, volume=1_000
    )
    current = ChargeLine(
        service=ServiceType.COLD_WATER, amount=2_000, tariff=200_000, volume=1_000
    )

    result = breakdown([current], [previous])

    line = result.lines[0]
    assert line.delta == 1_000
    assert line.tariff_effect == 1_000
    assert line.volume_effect == 0


def test_volume_only_change_gives_zero_tariff_effect() -> None:
    # тариф не меняется, меняется расход
    previous = ChargeLine(
        service=ServiceType.COLD_WATER, amount=500, tariff=100_000, volume=500
    )
    current = ChargeLine(
        service=ServiceType.COLD_WATER, amount=800, tariff=100_000, volume=800
    )

    result = breakdown([current], [previous])

    line = result.lines[0]
    assert line.delta == 300
    assert line.tariff_effect == 0
    assert line.volume_effect == 300


def test_appeared_line_is_classified_and_signed_correctly() -> None:
    current = ChargeLine(
        service=ServiceType.RECALCULATION, amount=1_234, tariff=None, volume=None
    )

    result = breakdown([current], [])

    line = result.lines[0]
    assert line.kind == "appeared"
    assert line.delta == 1_234
    assert line.tariff_effect == 0
    assert line.volume_effect == 1_234


def test_disappeared_line_is_classified_and_signed_correctly() -> None:
    previous = ChargeLine(
        service=ServiceType.PENALTY, amount=987, tariff=None, volume=None
    )

    result = breakdown([], [previous])

    line = result.lines[0]
    assert line.kind == "disappeared"
    assert line.delta == -987
    assert line.tariff_effect == 0
    assert line.volume_effect == -987


def test_lump_sum_line_without_a_tariff_puts_everything_into_volume_effect() -> None:
    # содержание жилья - разовая сумма, без тарифа и объема
    previous = ChargeLine(service=ServiceType.MAINTENANCE, amount=1_400)
    current = ChargeLine(service=ServiceType.MAINTENANCE, amount=1_500)

    result = breakdown([current], [previous])

    line = result.lines[0]
    assert line.kind == "changed"
    assert line.delta == 100
    assert line.tariff_effect == 0
    assert line.volume_effect == 100


def test_lump_sum_line_without_a_volume_also_puts_everything_into_volume_effect() -> (
    None
):
    # тариф есть (например, норматив), а объема нет - тот же случай
    previous = ChargeLine(service=ServiceType.MAINTENANCE, amount=1_400, tariff=100_000)
    current = ChargeLine(service=ServiceType.MAINTENANCE, amount=1_500, tariff=100_000)

    result = breakdown([current], [previous])

    line = result.lines[0]
    assert line.tariff_effect == 0
    assert line.volume_effect == 100


def test_lines_are_sorted_by_absolute_delta_descending() -> None:
    small = ChargeLine(service=ServiceType.GAS, amount=110, tariff=None, volume=None)
    small_prev = ChargeLine(
        service=ServiceType.GAS, amount=100, tariff=None, volume=None
    )
    big = ChargeLine(
        service=ServiceType.ELECTRICITY, amount=5_000, tariff=None, volume=None
    )
    negative = ChargeLine(
        service=ServiceType.HEATING, amount=200, tariff=None, volume=None
    )
    negative_prev = ChargeLine(
        service=ServiceType.HEATING, amount=3_000, tariff=None, volume=None
    )

    result = breakdown(
        [small, big, negative],
        [small_prev, negative_prev],
    )

    assert [line.service for line in result.lines] == [
        ServiceType.ELECTRICITY,
        ServiceType.HEATING,
        ServiceType.GAS,
    ]


def test_total_delta_is_the_sum_of_line_deltas() -> None:
    current = [
        ChargeLine(service=ServiceType.COLD_WATER, amount=1_000),
        ChargeLine(service=ServiceType.MAINTENANCE, amount=500),
    ]
    previous = [
        ChargeLine(service=ServiceType.COLD_WATER, amount=900),
        ChargeLine(service=ServiceType.WASTE, amount=200),
    ]

    result = breakdown(current, previous)

    assert result.delta == sum(line.delta for line in result.lines)
    assert result.delta == 100 + 500 - 200


# ---------------------------------------------------------------------------
# parse_lines - форма charges.lines из seed
# ---------------------------------------------------------------------------


def test_parse_line_reads_the_seed_shape() -> None:
    line = parse_line(
        {
            "service": "cold_water",
            "amount": 1_000,
            "volume": 5_000,
            "tariff": 100_000,
            "unit": "m3",
            "note": None,
        }
    )

    assert line == ChargeLine(
        service=ServiceType.COLD_WATER,
        amount=1_000,
        volume=5_000,
        tariff=100_000,
        unit="m3",
        note=None,
    )


def test_parse_line_defaults_missing_optional_keys_to_none() -> None:
    line = parse_line({"service": "maintenance", "amount": 500})

    assert line.volume is None
    assert line.tariff is None
    assert line.unit is None
    assert line.note is None


def test_parse_line_raises_invalid_value_for_an_unknown_service() -> None:
    with pytest.raises(InvalidValue):
        parse_line({"service": "space_heating", "amount": 100})


def test_parse_lines_parses_every_item() -> None:
    lines = parse_lines(
        [
            {"service": "cold_water", "amount": 100},
            {"service": "waste", "amount": 50},
        ]
    )

    assert [line.service for line in lines] == [
        ServiceType.COLD_WATER,
        ServiceType.WASTE,
    ]


# ---------------------------------------------------------------------------
# previous_period
# ---------------------------------------------------------------------------


def test_previous_period_shifts_one_month_back() -> None:
    assert previous_period(date(2026, 3, 1)) == date(2026, 2, 1)


def test_previous_period_wraps_across_a_year_boundary() -> None:
    assert previous_period(date(2026, 1, 1)) == date(2025, 12, 1)
