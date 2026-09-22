from dataclasses import field
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from zheka.base import ZhekaMutableType, Zoned
from zheka.core.ids import FlatId, HouseId, OrgId

_UNSET_AT = cast(datetime, None)
_UNSET_HOUSE_ID = cast(HouseId, None)
_UNSET_FLAT_ID = cast(FlatId, None)


class House(ZhekaMutableType, Zoned):
    id: HouseId = _UNSET_HOUSE_ID
    created_at: datetime = _UNSET_AT
    org_id: OrgId | None = None
    region: str
    city: str
    street: str
    building: str
    cadastral_no: str | None = None
    built_year: int | None = None
    floors: int | None = None
    area: int | None = None
    entrances: int = 1
    lat: Decimal | None = None
    lon: Decimal | None = None
    chat_binding_code: str
    overhaul: Any = field(default_factory=dict)
    documents: Any = field(default_factory=list)
    timezone: str

    @property
    def address(self) -> str:
        return f"{self.city}, {self.street}, {self.building}"


class Flat(ZhekaMutableType):
    id: FlatId = _UNSET_FLAT_ID
    house_id: HouseId
    number: str
    entrance: int | None = None
    area: int | None = None
    account_no: str | None = None
