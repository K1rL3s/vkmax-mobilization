import random
from collections.abc import Mapping
from datetime import datetime, timedelta

from zheka.base import ZhekaType
from zheka.core.enums import ServiceType
from zheka.core.models import House

DEMO_COMPANY = "Демо-РСО"
HINT_NOTE = "Это оценка, не юридическая консультация"

DEMO_REASONS: Mapping[ServiceType, str] = {
    ServiceType.HOT_WATER: "Плановая промывка системы горячего водоснабжения",
    ServiceType.COLD_WATER: "Ремонт водопровода на вводе в дом",
    ServiceType.ELECTRICITY: "Замена кабеля в трансформаторной подстанции",
    ServiceType.GAS: "Проверка газового оборудования",
    ServiceType.HEATING: "Гидравлические испытания тепловой сети",
}
RECALC_HINTS: Mapping[ServiceType, str] = {
    ServiceType.HOT_WATER: (
        "Перерыв в ГВС дольше 4 ч подряд или 8 ч за месяц, не считая ежегодной "
        "профилактики до 14 суток: плата за месяц снижается на 0,15% за каждый "
        "час сверх нормы (ПП 354, прил. 1, п. 4)"
    ),
    ServiceType.COLD_WATER: (
        "Перерыв в ХВС дольше 4 ч подряд или 8 ч за месяц: плата за месяц "
        "снижается на 0,15% за каждый час сверх нормы (ПП 354, прил. 1, п. 1)"
    ),
    ServiceType.ELECTRICITY: (
        "Перерыв в электроснабжении дольше 24 ч при одном источнике питания: "
        "плата снижается на 0,15% за каждый час сверх нормы (ПП 354, прил. 1, п. 9)"
    ),
    ServiceType.GAS: (
        "Перерыв в газоснабжении дольше 4 ч за месяц: плата снижается на 0,15% "
        "за каждый час сверх нормы (ПП 354, прил. 1, п. 11)"
    ),
    ServiceType.HEATING: (
        "Перерыв в отоплении дольше 16 ч подряд или 24 ч за месяц: плата "
        "снижается на 0,15% за каждый час сверх нормы (ПП 354, прил. 1, п. 14)"
    ),
}


class OutageView(ZhekaType):
    resource: ServiceType
    reason: str
    company: str
    starts_at: datetime
    ends_at: datetime
    recalc_hint: str
    is_demo: bool = True


def demo_outages(house: House, now: datetime) -> list[OutageView]:
    today = house.local(now).date()
    rng = random.Random(f"{house.id}:{today.isoformat()}")
    current, planned = rng.sample(list(DEMO_REASONS), 2)
    start = house.day_start(today) + timedelta(hours=rng.randint(6, 9))
    tomorrow = house.day_start(today + timedelta(days=1)) + timedelta(hours=10)
    outages = [
        _outage(current, start, start + timedelta(hours=rng.randint(10, 14))),
        _outage(planned, tomorrow, tomorrow + timedelta(hours=rng.randint(4, 8))),
    ]
    return [outage for outage in outages if outage.ends_at > now]


def _outage(
    resource: ServiceType,
    starts_at: datetime,
    ends_at: datetime,
) -> OutageView:
    return OutageView(
        resource=resource,
        reason=DEMO_REASONS[resource],
        company=DEMO_COMPANY,
        starts_at=starts_at,
        ends_at=ends_at,
        recalc_hint=f"{RECALC_HINTS[resource]}. {HINT_NOTE}",
    )
