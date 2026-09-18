import math
import secrets
from collections.abc import Sequence
from decimal import Decimal

from zheka.base import ZhekaType
from zheka.core.enums import (
    EventSource,
    EventType,
    ResidentRole,
    VerificationStatus,
)
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import FlatId, HouseId, OrgId, ResidentId, UserId
from zheka.core.models import Flat, House, Organization, Resident, User
from zheka.core.services.events import EventsService
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

# один градус широты в метрах, грубо. Сжатие долготы к полюсам учитывает
# множитель cos(широты), а потолок радиуса задает сам запрос
NEARBY_METERS_PER_DEGREE = 111_320

CONSENT_REQUIRED = "Сначала примите согласие на обработку персональных данных"
SEARCH_NEEDS_ADDRESS = "Укажите адрес или город"
FLAT_ID_AND_NUMBER = "Укажите либо квартиру из списка, либо ее номер"
FLAT_CHANGE_REFUSED = "Квартира уже подтверждена, переезд оформляет УК"


def stated(value: str | None) -> str | None:
    # строка из пробелов приходит от пустого поля формы и означает то же,
    # что и отсутствие параметра
    return None if value is None or not value.strip() else value.strip()


def is_connected(house: House, org: Organization | None) -> bool:
    # дом без УК и УК, не дошедшая до регистрации, для жителя одно и то же
    return (
        house.org_id is not None and org is not None and org.registered_at is not None
    )


class HouseFound(ZhekaType):
    house: House
    org: Organization | None
    is_connected: bool
    distance_m: int | None = None


class ResidencyView(ZhekaType):
    resident: Resident
    house: House
    flat: Flat | None
    is_connected: bool
    # статус последнего запроса подтверждения по квартире привязки: экран
    # подтверждения решает по нему, что показать, еще до карточки квартиры
    verification_status: VerificationStatus | None = None
    verification_reject_reason: str | None = None


class HouseCardData(ZhekaType):
    house: House
    org: Organization | None
    residency: ResidencyView | None
    is_connected: bool
    demand_count: int
    demand_sent: bool
    is_chat_bound: bool


class HouseResidentView(ZhekaType):
    resident: Resident
    user: User
    flat: Flat | None


class AdminHouseRow(ZhekaType):
    house: House
    flats_count: int
    residents_count: int
    open_requests: int
    chat_bound: bool


class AdminHouseCardData(ZhekaType):
    house: House
    flats_count: int
    residents_count: int
    verified_residents_count: int
    pending_verifications: int
    open_requests: int
    chat_bound: bool
    chat_title: str | None
    chairman_name: str | None


class HousesService:
    __slots__ = ("_events", "_flats", "_houses", "_orgs", "_residents", "_users")

    def __init__(
        self,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        orgs_repo: OrgsRepo,
        users_repo: UsersRepo,
        flats_repo: FlatsRepo,
        events_service: EventsService,
    ) -> None:
        self._houses = houses_repo
        self._residents = residents_repo
        self._orgs = orgs_repo
        self._users = users_repo
        self._flats = flats_repo
        self._events = events_service

    async def cities(
        self,
        region: str | None,
        query: str | None,
    ) -> Sequence[tuple[str, str]]:
        return await self._houses.list_cities(region, query)

    async def streets(
        self,
        city: str,
        region: str | None,
        query: str | None,
    ) -> Sequence[str]:
        return await self._houses.list_streets(city, region, query)

    async def search(
        self,
        user_id: UserId,
        city: str | None,
        street: str | None,
        building: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[HouseFound], int]:
        city, street, building, query = (
            stated(city),
            stated(street),
            stated(building),
            stated(query),
        )
        # без города и без строки поиска запрос перебрал бы весь справочник
        if city is None and query is None:
            raise InvalidRequest(SEARCH_NEEDS_ADDRESS)

        houses, total = await self._houses.search(
            city,
            street,
            building,
            query,
            limit,
            offset,
        )
        await self._events.record(
            EventType.HOUSE_SEARCH,
            user_id=user_id,
            method="picker" if query is None else "query",
            city=city,
            street=street,
            query=query,
        )
        return await self._with_orgs(houses), total

    async def nearest(
        self,
        user_id: UserId,
        lat: float,
        lon: float,
        radius_m: int,
        limit: int,
    ) -> list[HouseFound]:
        rows = await self._houses.nearest(
            Decimal(str(lat)),
            Decimal(str(lon)),
            Decimal(str(math.cos(math.radians(lat)))),
            Decimal(radius_m) / NEARBY_METERS_PER_DEGREE,
            limit,
        )
        found = await self._with_orgs([house for house, _ in rows])
        await self._events.record(
            EventType.HOUSE_SEARCH,
            user_id=user_id,
            method="geo",
            found=len(found),
        )
        return [
            HouseFound(
                house=item.house,
                org=item.org,
                is_connected=item.is_connected,
                distance_m=round(math.sqrt(float(distance)) * NEARBY_METERS_PER_DEGREE),
            )
            for item, (_, distance) in zip(found, rows, strict=True)
        ]

    async def house_card(self, house_id: HouseId, user_id: UserId) -> HouseCardData:
        house = await self._get_house(house_id)
        org = await self._org_of(house)
        connected = is_connected(house, org)
        resident = await self._residents.get_for_house(user_id, house_id)
        return HouseCardData(
            house=house,
            org=org,
            residency=(
                None
                if resident is None
                else await self._view(resident, house, connected)
            ),
            is_connected=connected,
            # счетчик спроса и своя отметка живут только в состоянии
            # «дом без подключенной УК»
            demand_count=0 if connected else await self._houses.count_demand(house_id),
            demand_sent=(
                not connected
                and await self._houses.has_demand_signal(house_id, user_id)
            ),
            is_chat_bound=await self._houses.is_chat_bound(house_id),
        )

    async def link(
        self,
        user_id: UserId,
        house_id: HouseId,
        flat_id: FlatId | None,
        flat_number: str | None,
        role: ResidentRole,
        source: EventSource,
        entrance: int | None,
    ) -> ResidencyView:
        number = stated(flat_number)
        if flat_id is not None and number is not None:
            raise InvalidRequest(FLAT_ID_AND_NUMBER)

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise EntityNotFound("Пользователь не найден")
        # согласие одно на сервис, а не по одному на дом
        if user.consent_at is None:
            raise NotEnoughRights(CONSENT_REQUIRED)

        house = await self._get_house(house_id)
        if flat_id is not None:
            flat = await self._houses.get_flat(flat_id)
            if flat is None or flat.house_id != house_id:
                raise EntityNotFound("Квартира не найдена")
        if number is not None:
            # номер уже заведенной квартиры превращается в привязку к ней,
            # иначе у дома завелся бы второй житель той же квартиры без flat_id
            known = await self._houses.get_flat_by_number(house_id, number)
            if known is not None:
                flat_id, number = FlatId(known.id), None

        existing = await self._residents.get_for_house(user_id, house_id)
        self._ensure_can_take_flat(existing, flat_id, number)

        resident, created = await self._residents.add_or_get(
            user_id,
            house_id,
            flat_id,
            number,
            role,
        )
        if created:
            await self._events.record(
                EventType.HOUSE_LINKED,
                user_id=user_id,
                house_id=house_id,
                flat_id=flat_id,
                flat_number=number,
                source=source.value,
                entrance=entrance,
            )
        return await self._view(
            resident,
            house,
            is_connected(house, await self._org_of(house)),
        )

    async def unlink(self, user_id: UserId, resident_id: ResidentId) -> None:
        resident = await self._residents.get(resident_id)
        # чужая привязка отвечает 404, а не 403: 403 подтвердил бы, что такой
        # resident_id существует, а в пути нет ничего о том, чей он
        if resident is None or resident.user_id != user_id:
            raise EntityNotFound("Привязка к дому не найдена")

        house_id = HouseId(resident.house_id)
        # удаляется только строка жителя: заявки, показания и голоса остаются
        await self._residents.delete(resident)
        await self._events.record(
            EventType.HOUSE_LEFT,
            user_id=user_id,
            house_id=house_id,
        )

    async def demand_signal(self, user_id: UserId, house_id: HouseId) -> int:
        house = await self._get_house(house_id)
        if is_connected(house, await self._org_of(house)):
            raise InvalidState("У дома уже есть подключенная УК")

        await self._houses.add_demand_signal(house_id, user_id)
        total = await self._houses.count_demand(house_id)
        await self._events.record(
            EventType.DEMAND_SIGNAL,
            user_id=user_id,
            house_id=house_id,
            total=total,
        )
        return total

    async def flats(
        self,
        user_id: UserId,
        house_id: HouseId,
        query: str | None,
        entrance: int | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Flat], int, set[FlatId]]:
        # is_taken показывает, в каких квартирах дома уже есть наши
        # пользователи, поэтому список квартир закрыт жителями этого дома.
        # Зависимость маршрута проверяет то же самое раньше, но сервис зовут
        # и мимо нее, а чужой дом отвечает 404, а не 403
        resident = await self._residents.get_for_house(user_id, house_id)
        if resident is None:
            raise EntityNotFound("Дом не найден")

        flats, total = await self._houses.list_flats(
            house_id,
            query,
            entrance,
            limit,
            offset,
        )
        residents = await self._residents.list_for_house(house_id)
        taken = {
            FlatId(resident.flat_id)
            for resident in residents
            if resident.flat_id is not None
        }
        return flats, total, taken

    def _ensure_can_take_flat(
        self,
        existing: Resident | None,
        flat_id: FlatId | None,
        flat_number: str | None,
    ) -> None:
        # квартиру житель выбирает на первом же экране, до всякого
        # подтверждения, поэтому до него повторная привязка ее и меняет.
        # Из подтвержденной квартиры жителя уводит только УК
        if existing is None or existing.flat_id is None or existing.verified_at is None:
            return
        if flat_number is not None or (
            flat_id is not None and flat_id != existing.flat_id
        ):
            raise InvalidState(FLAT_CHANGE_REFUSED)

    async def _get_house(self, house_id: HouseId) -> House:
        house = await self._houses.get(house_id)
        if house is None:
            raise EntityNotFound("Дом не найден")
        return house

    async def _org_of(self, house: House) -> Organization | None:
        if house.org_id is None:
            return None
        return await self._orgs.get(OrgId(house.org_id))

    async def _view(
        self,
        resident: Resident,
        house: House,
        connected: bool,
    ) -> ResidencyView:
        flat = (
            None
            if resident.flat_id is None
            else await self._houses.get_flat(FlatId(resident.flat_id))
        )
        return ResidencyView(
            resident=resident,
            house=house,
            flat=flat,
            is_connected=connected,
        )

    async def _with_orgs(self, houses: Sequence[House]) -> list[HouseFound]:
        org_ids = {OrgId(house.org_id) for house in houses if house.org_id is not None}
        orgs = {org.id: org for org in await self._orgs.list_by_ids(org_ids)}
        found = []
        for house in houses:
            org = None if house.org_id is None else orgs.get(OrgId(house.org_id))
            found.append(
                HouseFound(house=house, org=org, is_connected=is_connected(house, org)),
            )
        return found

    async def org_houses(
        self,
        org_id: OrgId,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminHouseRow], int]:
        houses, total = await self._houses.search_for_org(org_id, query, limit, offset)
        house_ids = [HouseId(house.id) for house in houses]
        flats = await self._houses.count_flats_by_house(house_ids)
        residents = await self._residents.count_by_house(house_ids)
        open_requests = await self._houses.count_open_requests_by_house(house_ids)
        chats = await self._houses.bound_chat_titles(house_ids)
        rows = [
            AdminHouseRow(
                house=house,
                flats_count=flats.get(HouseId(house.id), 0),
                residents_count=residents.get(HouseId(house.id), 0),
                open_requests=open_requests.get(HouseId(house.id), 0),
                chat_bound=HouseId(house.id) in chats,
            )
            for house in houses
        ]
        return rows, total

    async def admin_card(
        self,
        org_id: OrgId,
        house_id: HouseId,
    ) -> AdminHouseCardData:
        house = await self._org_house(org_id, house_id)
        chats = await self._houses.bound_chat_titles([house_id])
        chairman = await self._residents.get_chairman(house_id)
        chairman_user = (
            None
            if chairman is None
            else await self._users.get_by_id(UserId(chairman.user_id))
        )
        counts = await self._houses.count_flats_by_house([house_id])
        residents = await self._residents.count_by_house([house_id])
        open_requests = await self._houses.count_open_requests_by_house([house_id])
        return AdminHouseCardData(
            house=house,
            flats_count=counts.get(house_id, 0),
            residents_count=residents.get(house_id, 0),
            verified_residents_count=await self._residents.count_verified(house_id),
            pending_verifications=await self._flats.count_pending_verifications(
                house_id,
            ),
            open_requests=open_requests.get(house_id, 0),
            chat_bound=house_id in chats,
            chat_title=chats.get(house_id),
            chairman_name=None if chairman_user is None else chairman_user.name,
        )

    async def rotate_binding_code(self, org_id: OrgId, house_id: HouseId) -> House:
        house = await self._org_house(org_id, house_id)
        # houses.chat_binding_code - это String(8), token_hex(4) дает ровно 8
        await self._houses.set_binding_code(house, secrets.token_hex(4))
        return house

    async def house_residents(
        self,
        org_id: OrgId,
        house_id: HouseId,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[HouseResidentView], int]:
        await self._org_house(org_id, house_id)
        residents, total = await self._residents.search_for_house(
            house_id,
            query,
            limit,
            offset,
        )
        return await self._resident_views(residents), total

    async def _org_house(self, org_id: OrgId, house_id: HouseId) -> House:
        # house_id приходит из пути: дом чужой организации отвечает 404,
        # а не 403 - 403 подтвердил бы, что такой дом есть
        house = await self._houses.get_for_org(house_id, org_id)
        if house is None:
            raise EntityNotFound("Дом не найден")
        return house

    async def _resident_views(
        self,
        residents: Sequence[Resident],
    ) -> list[HouseResidentView]:
        users = {
            user.id: user
            for user in await self._users.list_by_ids(
                [UserId(resident.user_id) for resident in residents],
            )
        }
        flats = {
            flat.id: flat
            for flat in await self._houses.list_flats_by_ids(
                [
                    FlatId(resident.flat_id)
                    for resident in residents
                    if resident.flat_id is not None
                ],
            )
        }
        return [
            HouseResidentView(
                resident=resident,
                user=users[resident.user_id],
                flat=None if resident.flat_id is None else flats[resident.flat_id],
            )
            for resident in residents
        ]
