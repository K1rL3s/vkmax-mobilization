from datetime import date, datetime
from typing import Any

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.enums import ServiceType
from zheka.core.ids import ChargeId, FlatId, HouseId, TariffId


class Tariff(ZhekaMutableType):
    id: TariffId = UNSET
    house_id: HouseId
    service: ServiceType
    value: int
    unit: str
    valid_from: date
    document_url: str | None = None


class Charge(ZhekaMutableType):
    id: ChargeId = UNSET
    created_at: datetime = UNSET
    flat_id: FlatId
    period: date
    lines: Any
    total: int
    is_closed: bool = True
    paid_at: datetime | None = None
