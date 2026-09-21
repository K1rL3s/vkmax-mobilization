from datetime import date, datetime
from typing import Any, cast

from zheka.base import ZhekaMutableType
from zheka.core.enums import ServiceType
from zheka.core.ids import ChargeId, FlatId, HouseId, TariffId

_UNSET_AT = cast(datetime, None)
_UNSET_TARIFF_ID = cast(TariffId, None)
_UNSET_CHARGE_ID = cast(ChargeId, None)


class Tariff(ZhekaMutableType):
    id: TariffId = _UNSET_TARIFF_ID
    house_id: HouseId
    service: ServiceType
    value: int
    unit: str
    valid_from: date
    document_url: str | None = None


class Charge(ZhekaMutableType):
    id: ChargeId = _UNSET_CHARGE_ID
    created_at: datetime = _UNSET_AT
    flat_id: FlatId
    period: date
    lines: Any
    total: int
    is_closed: bool = True
    paid_at: datetime | None = None
