from datetime import datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema, FreeText
from zheka.api.schemas.files import FileRef
from zheka.core.enums import (
    EventSource,
    RequestCategory,
    ResidentRole,
    ResidentStatus,
    ServiceType,
    VerificationStatus,
)
from zheka.core.ids import FlatId, HouseId, OrgId, ResidentId, UserId
from zheka.core.models import Flat
from zheka.core.services.house_point import HouseAtPoint
from zheka.core.services.houses import (
    AdminHouseCardData,
    AdminHouseRow,
    HouseCardData,
    HouseFound,
    HouseResidentView,
    ResidencyView,
)


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
    emergency_phone: str | None = Field(
        default=None,
        description="Аварийно-диспетчерская служба дома, если УК ее указала",
    )
    is_demo: bool = False
    timezone: str = Field(
        description="Часовой пояс IANA: в нем приемные часы и слоты записи",
    )


class HouseListItem(BaseSchema):
    id: HouseId
    address: str
    city: str
    street: str
    building: str
    is_connected: bool
    org_name: str | None = None
    distance_m: int | None = None
    lat: float | None = None
    lon: float | None = None

    @classmethod
    def of(cls, found: HouseFound) -> Self:
        house = found.house
        return cls(
            id=house.id,
            address=house.address,
            city=house.city,
            street=house.street,
            building=house.building,
            is_connected=found.is_connected,
            org_name=None if found.org is None else found.org.name,
            distance_m=found.distance_m,
            lat=None if house.lat is None else float(house.lat),
            lon=None if house.lon is None else float(house.lon),
        )


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
    verification_status: VerificationStatus | None = None
    verification_reject_reason: str | None = None

    @classmethod
    def of(cls, view: ResidencyView) -> Self:
        resident = view.resident
        return cls(
            resident_id=resident.id,
            house_id=resident.house_id,
            address=view.house.address,
            role=resident.role,
            status=resident.status,
            verified=resident.verified_at is not None,
            is_chairman=resident.is_chairman,
            can_see_charges=resident.can_see_charges,
            can_vote=resident.can_vote,
            is_connected=view.is_connected,
            flat_id=None if view.flat is None else view.flat.id,
            flat_number=(
                resident.flat_number if view.flat is None else view.flat.number
            ),
            verification_status=view.verification_status,
            verification_reject_reason=view.verification_reject_reason,
        )


class OverhaulWork(BaseSchema):
    title: str
    year: int
    is_done: bool


class HouseOverhaul(BaseSchema):
    program: str | None = None
    works: list[OverhaulWork]


class OrgPublicStats(BaseSchema):
    closed: int = Field(description="Заявок сдано на приемку, по всем домам УК")
    on_time: int = Field(description="Из них сдано в нормативный срок")
    on_time_share: int = Field(
        description="Доля сданных в срок в сотых долях процента, 50% это 5000",
    )
    accept_time: int | None = Field(
        default=None,
        description="Среднее время до принятия заявки в минутах",
    )
    accept_time_median: int | None = Field(
        default=None,
        description="Медиана времени до принятия заявки в минутах",
    )
    rating: int | None = Field(
        default=None,
        description="Средняя оценка жителей в сотых долях балла",
    )
    ratings_count: int


class OutageItem(BaseSchema):
    resource: ServiceType
    reason: str
    company: str
    starts_at: datetime
    ends_at: datetime
    recalc_hint: str = Field(description="Норма перерасчета по ПП 354, без расчета")
    is_demo: bool = Field(description="Отключение выдумано для демонстрации")


class HouseCard(BaseSchema):
    id: HouseId
    address: str
    region: str
    city: str
    street: str
    building: str
    cadastral_no: str | None
    entrances: int
    is_connected: bool
    demand_count: int
    demand_sent: bool
    built_year: int | None = None
    floors: int | None = None
    area: int | None = Field(
        default=None,
        description="Площадь в сотых долях квадратного метра",
    )
    lat: float | None = None
    lon: float | None = None
    org: OrgContacts | None = None
    my_residency: ResidencySummary | None = None
    chat_binding_code: str | None = None
    chat_bound: bool = False
    overhaul: HouseOverhaul | None = None
    documents: list[FileRef]
    org_stats: OrgPublicStats | None = Field(
        default=None,
        description="Показатели УК за 90 дней, нет при малом числе заявок",
    )
    outages: list[OutageItem] = Field(
        description="Текущие и плановые отключения по дому, сейчас демо-данные",
    )

    @classmethod
    def of(cls, card: HouseCardData, documents: list[FileRef]) -> Self:
        house = card.house
        residency = card.residency
        is_chairman = residency is not None and residency.resident.is_chairman
        return cls(
            id=house.id,
            address=house.address,
            region=house.region,
            city=house.city,
            street=house.street,
            building=house.building,
            cadastral_no=house.cadastral_no,
            entrances=house.entrances,
            is_connected=card.is_connected,
            demand_count=card.demand_count,
            demand_sent=card.demand_sent,
            built_year=house.built_year,
            floors=house.floors,
            area=house.area,
            lat=None if house.lat is None else float(house.lat),
            lon=None if house.lon is None else float(house.lon),
            org=None if card.org is None else OrgContacts.model_validate(card.org),
            my_residency=(
                None if residency is None else ResidencySummary.of(residency)
            ),
            chat_binding_code=house.chat_binding_code if is_chairman else None,
            chat_bound=card.is_chat_bound,
            overhaul=(
                HouseOverhaul.model_validate(house.overhaul) if house.overhaul else None
            ),
            documents=documents,
            org_stats=(
                None
                if card.org_stats is None
                else OrgPublicStats.model_validate(card.org_stats)
            ),
            outages=[OutageItem.model_validate(item) for item in card.outages],
        )


class FlatListItem(BaseSchema):
    id: FlatId
    number: str
    entrance: int | None = None
    area: int | None = Field(
        default=None,
        description="Площадь в сотых долях квадратного метра",
    )
    is_taken: bool = False

    @classmethod
    def of(cls, flat: Flat, is_taken: bool) -> Self:
        return cls(
            id=flat.id,
            number=flat.number,
            entrance=flat.entrance,
            area=flat.area,
            is_taken=is_taken,
        )


class LinkHouseRequest(BaseSchema):
    flat_id: FlatId | None = None
    flat_number: str | None = None
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

    @classmethod
    def of(cls, row: AdminHouseRow) -> Self:
        return cls(
            id=row.house.id,
            address=row.house.address,
            entrances=row.house.entrances,
            flats_count=row.flats_count,
            residents_count=row.residents_count,
            open_requests=row.open_requests,
            chat_bound=row.chat_bound,
        )


class EntranceQr(BaseSchema):
    entrance: int
    code: str
    deeplink: str


class ObjectQr(BaseSchema):
    entrance: int
    category: RequestCategory
    deeplink: str = Field(description="Ссылка startapp на форму заявки")


class AdminHouseCard(BaseSchema):
    id: HouseId
    address: str
    region: str
    city: str
    street: str
    building: str
    cadastral_no: str | None
    entrances: int
    flats_count: int
    residents_count: int
    verified_residents_count: int
    pending_verifications: int
    open_requests: int
    chat_bound: bool
    chat_binding_code: str
    entrance_qrs: list[EntranceQr]
    object_qrs: list[ObjectQr] = Field(
        description="QR на объектах подъезда: лифт, свет, уборка",
    )
    built_year: int | None = None
    floors: int | None = None
    area: int | None = Field(
        default=None,
        description="Площадь в сотых долях квадратного метра",
    )
    chairman_name: str | None = None
    chat_title: str | None = None

    @classmethod
    def of(
        cls,
        card: AdminHouseCardData,
        entrance_qrs: list[EntranceQr],
        object_qrs: list[ObjectQr] | None = None,
    ) -> Self:
        house = card.house
        return cls(
            id=house.id,
            address=house.address,
            region=house.region,
            city=house.city,
            street=house.street,
            building=house.building,
            cadastral_no=house.cadastral_no,
            entrances=house.entrances,
            flats_count=card.flats_count,
            residents_count=card.residents_count,
            verified_residents_count=card.verified_residents_count,
            pending_verifications=card.pending_verifications,
            open_requests=card.open_requests,
            chat_bound=card.chat_bound,
            chat_binding_code=house.chat_binding_code,
            entrance_qrs=entrance_qrs,
            object_qrs=object_qrs or [],
            built_year=house.built_year,
            floors=house.floors,
            area=house.area,
            chairman_name=card.chairman_name,
            chat_title=card.chat_title,
        )


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
    phone: str | None = None

    @classmethod
    def of(cls, view: HouseResidentView) -> Self:
        resident = view.resident
        return cls(
            resident_id=resident.id,
            user_id=resident.user_id,
            created_at=resident.created_at,
            name=view.user.name,
            role=resident.role,
            status=resident.status,
            verified=resident.verified_at is not None,
            is_chairman=resident.is_chairman,
            flat_id=None if view.flat is None else view.flat.id,
            flat_number=(
                resident.flat_number if view.flat is None else view.flat.number
            ),
            block_reason=resident.block_reason,
            phone=view.user.phone,
        )


class BlockResidentRequest(BaseSchema):
    reason: FreeText


class RevokeVerificationRequest(BaseSchema):
    reason: FreeText


class SetChairmanRequest(BaseSchema):
    is_chairman: bool


class BindingCodeResponse(BaseSchema):
    house_id: HouseId
    code: str
    deeplink: str


class PointAddress(BaseSchema):
    region: str
    city: str
    street: str
    building: str
    address: str


class HouseAtPointResponse(BaseSchema):
    house: HouseListItem | None = None
    address: PointAddress | None = Field(
        default=None,
        description="Адрес здания в точке, если дома нет в справочнике",
    )
    geocoder_failed: bool = Field(
        default=False,
        description="Сервис адресов не ответил, стоит повторить позже",
    )

    @classmethod
    def of(cls, found: HouseAtPoint) -> Self:
        address = found.address
        return cls(
            house=None if found.house is None else HouseListItem.of(found.house),
            address=(
                None
                if address is None
                else PointAddress(
                    region=address.region,
                    city=address.city,
                    street=address.street,
                    building=address.building,
                    address=address.address,
                )
            ),
            geocoder_failed=found.geocoder_failed,
        )


class AddHouseRequest(BaseSchema):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
