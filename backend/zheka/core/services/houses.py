import math
from collections.abc import Sequence
from decimal import Decimal

from zheka.base import ZhekaType
from zheka.core.enums import EventSource, EventType, ResidentRole
from zheka.core.errors import EntityNotFound, InvalidState, NotEnoughRights
from zheka.core.ids import FlatId, HouseId, OrgId, ResidentId, UserId
from zheka.core.models import Flat, House, Organization, Resident
from zheka.core.services.events import EventsService
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

# один градус широты в метрах, грубо. Сжатие долготы к полюсам учитывает
# множитель cos(широты), а потолок радиуса задает сам запрос
NEARBY_METERS_PER_DEGREE = 111_320

CONSENT_REQUIRED = "Сначала примите согласие на обработку персональных данных"


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


class HouseCardData(ZhekaType):
    house: House
    org: Organization | None
    residency: ResidencyView | None
    is_connected: bool
    demand_count: int
    demand_sent: bool
    is_chat_bound: bool


class HousesService:
    __slots__ = ("_events", "_houses", "_orgs", "_residents", "_users")

    def __init__(
        self,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        orgs_repo: OrgsRepo,
        users_repo: UsersRepo,
        events_service: EventsService,
    ) -> None:
        self._houses = houses_repo
        self._residents = residents_repo
        self._orgs = orgs_repo
        self._users = users_repo
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
        city: str,
        street: str | None,
        building: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[HouseFound], int]:
        houses, total = await self._houses.search(city, street, building, limit, offset)
        await self._events.record(
            EventType.HOUSE_SEARCH,
            user_id=user_id,
            method="picker",
            city=city,
            street=street,
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
        role: ResidentRole,
        source: EventSource,
        entrance: int | None,
    ) -> ResidencyView:
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

        # решение до записи: молча проигнорировать чужой flat_id нельзя, а
        # переселить жителя повторной привязкой тем более - квартиру меняет
        # подтверждение. Квартира, которой у жителя еще не было, проставляется
        existing = await self._residents.get_for_house(user_id, house_id)
        if (
            existing is not None
            and existing.flat_id is not None
            and flat_id is not None
            and existing.flat_id != flat_id
        ):
            raise InvalidState(
                "Квартира меняется через подтверждение, а не повторной привязкой",
            )

        resident, created = await self._residents.add_or_get(
            user_id,
            house_id,
            flat_id,
            role,
        )
        if created:
            await self._events.record(
                EventType.HOUSE_LINKED,
                user_id=user_id,
                house_id=house_id,
                flat_id=flat_id,
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
        house_id: HouseId,
        query: str | None,
        entrance: int | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Flat], int, set[FlatId]]:
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
