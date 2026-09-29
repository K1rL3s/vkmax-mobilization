import re
import secrets
from collections.abc import Collection
from decimal import Decimal
from typing import Protocol

from zheka.base import ZhekaType
from zheka.core.enums import EventType
from zheka.core.errors import InvalidRequest, TooManyRequests
from zheka.core.ids import UserId
from zheka.core.models import House
from zheka.core.regions import region_timezone
from zheka.core.services.events import EventsService
from zheka.core.services.houses import HouseFound, is_connected
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.nominatim import GeocoderUnavailable, ReverseAddress
from zheka.infra.quota import HouseAddQuota, HouseLookupQuota

MATCH_RADIUS_M = 25
ADDRESS_RADIUS_M = 200
ADDRESS_CANDIDATES = 20
COORDINATE_DIGITS = 6
NO_BUILDING = "Здесь не найден дом с номером, выберите здание на карте"
GEOCODER_FAILED = "Не удалось определить адрес, попробуйте еще раз"
TOO_MANY_HOUSES = "Слишком много новых домов, попробуйте через час"
_BUILDING_WORDS = (
    ("корпус", "к"),
    ("корп", "к"),
    ("строение", "с"),
    ("стр", "с"),
    ("литера", "лит"),
    ("литер", "лит"),
)
_DEFAULT_LITERA = "лита"


class Geocoder(Protocol):
    async def reverse(self, lat: float, lon: float) -> ReverseAddress | None: ...


def normalized_building(value: str) -> str:
    text = value.lower().replace("ё", "е")
    for word, short in _BUILDING_WORDS:
        text = re.sub(rf"\b{word}\b\.?", short, text)
    return re.sub(r"[\s.]", "", text).removesuffix(_DEFAULT_LITERA)


def normalized_street(value: str) -> str:
    text = re.sub(r"\(.*?\)", " ", value.lower().replace("ё", "е"))
    return " ".join(text.split())


class HouseAtPoint(ZhekaType):
    house: HouseFound | None = None
    address: ReverseAddress | None = None
    geocoder_failed: bool = False


class HousePointService:
    __slots__ = ("_events", "_geocoder", "_houses", "_lookups", "_orgs", "_quota")

    def __init__(
        self,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        geocoder: Geocoder,
        quota: HouseAddQuota,
        events_service: EventsService,
        lookup_quota: HouseLookupQuota,
    ) -> None:
        self._houses = houses_repo
        self._orgs = orgs_repo
        self._geocoder = geocoder
        self._quota = quota
        self._events = events_service
        self._lookups = lookup_quota

    async def at(self, user_id: UserId, lat: float, lon: float) -> HouseAtPoint:
        found = await self._resolve(user_id, lat, lon)
        await self._events.record(
            EventType.HOUSE_SEARCH,
            user_id=user_id,
            method="map",
            found=int(found.house is not None),
        )
        return found

    async def add(self, user_id: UserId, lat: float, lon: float) -> HouseFound:
        found = await self._resolve(user_id, lat, lon)
        if found.house is not None:
            return found.house
        if found.address is None:
            raise InvalidRequest(
                GEOCODER_FAILED if found.geocoder_failed else NO_BUILDING,
            )
        address = found.address
        await self._houses.lock_adding()
        twin = await self._matching(lat, lon, address)
        if twin is not None:
            return await self._found(twin)
        if not self._quota.take(user_id):
            raise TooManyRequests(TOO_MANY_HOUSES)
        house = await self._houses.add(
            House(
                region=await self._region(address),
                city=address.city,
                street=address.street,
                building=address.building,
                lat=Decimal(str(round(lat, COORDINATE_DIGITS))),
                lon=Decimal(str(round(lon, COORDINATE_DIGITS))),
                timezone=region_timezone(address.iso_region),
                chat_binding_code=secrets.token_hex(4),
                added_by_resident=True,
            ),
        )
        await self._events.record(
            EventType.HOUSE_ADDED,
            user_id=user_id,
            house_id=house.id,
        )
        return HouseFound(house=house, org=None, is_connected=False)

    async def _resolve(self, user_id: UserId, lat: float, lon: float) -> HouseAtPoint:
        near = await self._houses.nearest(lat, lon, MATCH_RADIUS_M, 1)
        if near:
            return HouseAtPoint(house=await self._found(near[0][0]))
        if not self._lookups.take(user_id):
            raise TooManyRequests
        try:
            address = await self._geocoder.reverse(lat, lon)
        except GeocoderUnavailable:
            return HouseAtPoint(geocoder_failed=True)
        if address is None:
            return HouseAtPoint()
        house = await self._matching(lat, lon, address)
        if house is None:
            return HouseAtPoint(address=address)
        return HouseAtPoint(house=await self._found(house))

    async def _found(self, house: House) -> HouseFound:
        org = None if house.org_id is None else await self._orgs.get(house.org_id)
        return HouseFound(house=house, org=org, is_connected=is_connected(house, org))

    async def _matching(
        self,
        lat: float,
        lon: float,
        address: ReverseAddress,
    ) -> House | None:
        street = normalized_street(address.street)
        building = normalized_building(address.building)
        near = await self._houses.nearest(
            lat,
            lon,
            ADDRESS_RADIUS_M,
            ADDRESS_CANDIDATES,
        )
        candidates = [house for house, _distance in near]
        candidates += await self._houses.unplaced(address.city)
        return next(
            (
                house
                for house in candidates
                if normalized_street(house.street) == street
                and normalized_building(house.building) == building
            ),
            None,
        )

    async def _region(self, address: ReverseAddress) -> str:
        cities = await self._houses.list_cities(None, None)
        return directory_region(address.region, {region for region, _ in cities})


def directory_region(region: str, known: Collection[str]) -> str:
    words = _words(region)
    return next(
        (
            name
            for name in sorted(known)
            if words <= _words(name) or _words(name) <= words
        ),
        region,
    )


def _words(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"\w+(?:-\w+)*", value.lower().replace("ё", "е")))
