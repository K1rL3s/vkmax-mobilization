from datetime import date
from typing import Any

import pytest

from zheka.core.charges import (
    ChargeLine,
    breakdown,
    is_bill_question,
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


@pytest.mark.parametrize(
    ("previous", "current", "effects"),
    [
        pytest.param((2, 0, 5), (5, 33_334, 7), (3, 2, 1), id="naive-rounding"),
        pytest.param(
            (500, 100_000, 500),
            (800, 100_000, 800),
            (300, 0, 300),
            id="volume-only",
        ),
    ],
)
def test_effects_always_sum_to_the_line_delta_even_where_naive_rounding_breaks_it(
    previous: tuple[int, int, int],
    current: tuple[int, int, int],
    effects: tuple[int, int, int],
) -> None:
    def line_of(amount: int, tariff: int, volume: int) -> ChargeLine:
        return ChargeLine(
            service=ServiceType.COLD_WATER,
            amount=amount,
            tariff=tariff,
            volume=volume,
        )

    line = breakdown([line_of(*current)], [line_of(*previous)]).lines[0]

    assert (line.delta, line.tariff_effect, line.volume_effect) == effects


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
        (
            ChargeLine(service=ServiceType.MAINTENANCE, amount=1_500),
            ChargeLine(service=ServiceType.MAINTENANCE, amount=1_400),
            "changed",
            100,
        ),
        (
            ChargeLine(service=ServiceType.MAINTENANCE, amount=1_500, tariff=100_000),
            ChargeLine(service=ServiceType.MAINTENANCE, amount=1_400, tariff=100_000),
            "changed",
            100,
        ),
    ],
)
def test_a_line_without_a_tariff_effect_puts_the_delta_into_volume(
    current: ChargeLine | None,
    previous: ChargeLine | None,
    kind: str,
    delta: int,
) -> None:
    result = breakdown(
        [] if current is None else [current],
        [] if previous is None else [previous],
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
    raw: dict[str, Any],
    line: ChargeLine,
) -> None:
    assert parse_line(raw) == line


def test_parse_line_raises_invalid_value_for_an_unknown_service() -> None:
    with pytest.raises(InvalidValue):
        parse_line({"service": "space_heating", "amount": 100})


def test_previous_period_shifts_one_month_back_across_a_year() -> None:
    assert previous_period(date(2026, 3, 1)) == date(2026, 2, 1)
    assert previous_period(date(2026, 1, 1)) == date(2025, 12, 1)


@pytest.mark.parametrize(
    ("text", "asked"),
    [
        ("Почему так много?", True),
        ("Почему такой счёт", True),
        ("вырос счет за свет", True),
        ("Подорожало", True),
        ("Почему в этом месяце квитанция больше на две тысячи", True),
        ("Тарифы опять выросли?", True),
        ("Почему в этом месяце такой большой счёт?", True),
        ("Почему так много мусора у подъезда", False),
        ("Течет кран на кухне, вода по полу", False),
        ("Счетчик воды показывает больше обычного", False),
        ("Не пришла квитанция за сентябрь", False),
        ("Трава выросла во дворе, прошу покосить", False),
        ("Много воды в подвале", False),
        ("Почему так холодно в квартире", False),
        ("Сумма за свет неправильная, счётчик сломан", False),
        ("Большие счета, а горячей воды нет неделю", False),
        ("Плата за лифт большая, а лифт не работает", False),
        ("Тариф на вывоз мусора вырос, а мусор не вывозят", False),
        ("Сумма в квитанции завышена, прошу пересчитать", False),
        ("Почему так долго чинят трубу, а плата идет", False),
        ("Счет вырос, потому что счетчик неправильно считает", False),
        ("Почему такой большой счет, у нас течет стояк", False),
        ("Счет за газ стал больше, пахнет газом в подъезде", False),
        ("Плата за вывоз мусора выросла, а мусор лежит неделю", False),
        ("Тариф вырос, но подъезд убирают раз в месяц", False),
        ("Почему такой большой счет, не понимаю", True),
        ("Почему такая сумма в квитанции?", True),
        (
            (
                "Сломался лифт во втором подъезде, жильцы с детьми и пожилые "
                "не могут подняться, а счет за содержание лифта вырос, почините"
            ),
            False,
        ),
    ],
)
def test_only_a_clear_bill_phrase_is_a_bill_question(text: str, asked: bool) -> None:
    assert is_bill_question(text) is asked
