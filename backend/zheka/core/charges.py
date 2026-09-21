from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Literal

from zheka.base import ZhekaType
from zheka.core.enums import ServiceType
from zheka.core.errors import InvalidValue

# тысячные объема (1/1000 ед.) * тариф (1/10000 руб/ед.) = 1/10_000_000 руб =
# 1/100_000 копейки
_VOLUME_DIVISOR = 100_000
# сотые площади (1/100 кв.м) * тариф (1/10000 руб/ед.) = 1/1_000_000 руб =
# 1/10_000 копейки
_AREA_DIVISOR = 10_000

LineDeltaKind = Literal["changed", "appeared", "disappeared"]

UNKNOWN_SERVICE = "Неизвестная услуга в начислении"


def to_kopecks(product: int, *, is_area: bool = False) -> int:
    # единственная функция проекта, которая делит деньги: произведение двух
    # масштабированных целых переводится в копейки округлением вверх-от-половины
    divisor = _AREA_DIVISOR if is_area else _VOLUME_DIVISOR
    half = divisor // 2
    return (product + half) // divisor


class ChargeLine(ZhekaType):
    service: ServiceType
    amount: int  # копейки
    volume: int | None = None  # тысячные единицы измерения
    tariff: int | None = None  # 1/10000 рубля за единицу
    unit: str | None = None
    note: str | None = None


class LineDelta(ZhekaType):
    service: ServiceType
    delta: int  # копейки
    tariff_effect: int  # копейки, эффект от изменения тарифа на новый объем
    volume_effect: int  # копейки, остаток дельты после тарифного эффекта
    kind: LineDeltaKind


class ChargeBreakdown(ZhekaType):
    delta: int  # копейки, суммарная дельта по всем строкам
    lines: list[LineDelta]


def parse_line(raw: Mapping[str, Any]) -> ChargeLine:
    raw_service = raw["service"]
    try:
        service = ServiceType(raw_service)
    except ValueError as error:
        raise InvalidValue(f"{UNKNOWN_SERVICE}: {raw_service!r}") from error
    return ChargeLine(
        service=service,
        amount=raw["amount"],
        volume=raw.get("volume"),
        tariff=raw.get("tariff"),
        unit=raw.get("unit"),
        note=raw.get("note"),
    )


def parse_lines(raw: Sequence[Any]) -> list[ChargeLine]:
    return [parse_line(item) for item in raw]


def previous_period(period: date) -> date:
    month_index = period.year * 12 + (period.month - 1) - 1
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


def _changed_line(current: ChargeLine, previous: ChargeLine) -> LineDelta:
    delta = current.amount - previous.amount
    if (
        current.tariff is not None
        and previous.tariff is not None
        and current.volume is not None
    ):
        tariff_effect = to_kopecks((current.tariff - previous.tariff) * current.volume)
    else:
        # разовая сумма (содержание, пени) - тариф ни на что не множится,
        # вся дельта уходит в расходный эффект
        tariff_effect = 0
    return LineDelta(
        service=current.service,
        delta=delta,
        tariff_effect=tariff_effect,
        # вычитание, а не независимое произведение - тогда сумма двух эффектов
        # всегда равна дельте строки, даже после округления
        volume_effect=delta - tariff_effect,
        kind="changed",
    )


def _appeared_line(current: ChargeLine) -> LineDelta:
    return LineDelta(
        service=current.service,
        delta=current.amount,
        tariff_effect=0,
        volume_effect=current.amount,
        kind="appeared",
    )


def _disappeared_line(previous: ChargeLine) -> LineDelta:
    delta = -previous.amount
    return LineDelta(
        service=previous.service,
        delta=delta,
        tariff_effect=0,
        volume_effect=delta,
        kind="disappeared",
    )


def breakdown(
    current: Sequence[ChargeLine],
    previous: Sequence[ChargeLine],
) -> ChargeBreakdown:
    current_by_service = {line.service: line for line in current}
    previous_by_service = {line.service: line for line in previous}
    services = dict.fromkeys([*current_by_service, *previous_by_service])

    lines: list[LineDelta] = []
    for service in services:
        now = current_by_service.get(service)
        before = previous_by_service.get(service)
        if now is not None and before is not None:
            lines.append(_changed_line(now, before))
        elif now is not None:
            lines.append(_appeared_line(now))
        elif before is not None:
            lines.append(_disappeared_line(before))

    lines.sort(key=lambda line: abs(line.delta), reverse=True)
    return ChargeBreakdown(delta=sum(line.delta for line in lines), lines=lines)
