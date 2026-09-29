from dataclasses import field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from zheka.base import UNSET, ZhekaMutableType, Zoned
from zheka.core.ids import FlatId, HouseId, OrgId


class House(ZhekaMutableType, Zoned):
    id: HouseId = UNSET
    created_at: datetime = UNSET
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
    added_by_resident: bool = False
    digest_sent_on: date | None = None
    passport: Any = field(default_factory=dict)

    @property
    def address(self) -> str:
        return f"{self.city}, {self.street_address}"

    @property
    def street_address(self) -> str:
        return f"{self.street}, {self.building}"


class Flat(ZhekaMutableType):
    id: FlatId = UNSET
    house_id: HouseId
    number: str
    entrance: int | None = None
    area: int | None = None
    account_no: str | None = None
