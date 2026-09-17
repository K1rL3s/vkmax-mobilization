from datetime import datetime

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.files import FileRef
from zheka.core.enums import EventSource, ResidentRole, ResidentStatus
from zheka.core.ids import FlatId, HouseId, OrgId, ResidentId, UserId


class CityItem(BaseSchema):
    region: str
    city: str


class OrgContacts(BaseSchema):
    id: OrgId
    name: str
    phone: str
    address: str
    license_no: str | None = None
    reception_note: str | None = None
    is_demo: bool = False


class HouseListItem(BaseSchema):
    id: HouseId
    address: str
    city: str
    street: str
    building: str
    is_connected: bool
    org_name: str | None = None
    # заполняется только в поиске по геопозиции
    distance_m: int | None = None


class ResidencySummary(BaseSchema):
    resident_id: ResidentId
    house_id: HouseId
    address: str
    role: ResidentRole
    status: ResidentStatus
    verified: bool
    is_chairman: bool
    can_see_charges: bool
    can_vote: bool
    is_connected: bool
    flat_id: FlatId | None = None
    flat_number: str | None = None


class OverhaulWork(BaseSchema):
    title: str
    year: int
    is_done: bool


class HouseOverhaul(BaseSchema):
    program: str | None = None
    works: list[OverhaulWork]


class HouseCard(BaseSchema):
    id: HouseId
    address: str
    region: str
    city: str
    street: str
    building: str
    cadastral_no: str
    entrances: int
    is_connected: bool
    demand_count: int
    built_year: int | None = None
    floors: int | None = None
    area: int | None = Field(
        default=None, description="Площадь в сотых долях квадратного метра"
    )
    lat: float | None = None
    lon: float | None = None
    org: OrgContacts | None = None
    my_residency: ResidencySummary | None = None
    # код привязки чата заводит УК, житель видит его только как председатель
    chat_binding_code: str | None = None
    chat_bound: bool = False
    overhaul: HouseOverhaul | None = None
    documents: list[FileRef]


class FlatListItem(BaseSchema):
    id: FlatId
    number: str
    entrance: int | None = None
    area: int | None = Field(
        default=None, description="Площадь в сотых долях квадратного метра"
    )
    is_taken: bool = False


class LinkHouseRequest(BaseSchema):
    flat_id: FlatId | None = None
    role: ResidentRole = ResidentRole.OWNER
    account_no: str | None = None
    entrance: int | None = None
    source: EventSource = EventSource.MINIAPP


class DemandSignalResponse(BaseSchema):
    house_id: HouseId
    total: int


class AdminHouseListItem(BaseSchema):
    id: HouseId
    address: str
    entrances: int
    flats_count: int
    residents_count: int
    open_requests: int
    chat_bound: bool


class EntranceQr(BaseSchema):
    entrance: int
    code: str
    deeplink: str


class AdminHouseCard(BaseSchema):
    id: HouseId
    address: str
    region: str
    city: str
    street: str
    building: str
    cadastral_no: str
    entrances: int
    flats_count: int
    residents_count: int
    verified_residents_count: int
    pending_verifications: int
    open_requests: int
    chat_bound: bool
    # код привязки домового чата, его УК диктует жителю или председателю
    chat_binding_code: str
    entrance_qrs: list[EntranceQr]
    built_year: int | None = None
    floors: int | None = None
    area: int | None = Field(
        default=None,
        description="Площадь в сотых долях квадратного метра",
    )
    chairman_name: str | None = None
    chat_title: str | None = None


class HouseResidentItem(BaseSchema):
    resident_id: ResidentId
    user_id: UserId
    created_at: datetime
    name: str
    role: ResidentRole
    status: ResidentStatus
    verified: bool
    is_chairman: bool
    flat_id: FlatId | None = None
    flat_number: str | None = None
    block_reason: str | None = None


class BlockResidentRequest(BaseSchema):
    reason: str


class RevokeVerificationRequest(BaseSchema):
    reason: str


class SetChairmanRequest(BaseSchema):
    is_chairman: bool


class BindingCodeResponse(BaseSchema):
    house_id: HouseId
    code: str
    deeplink: str
