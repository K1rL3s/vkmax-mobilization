import asyncio
import json
import secrets
from collections.abc import AsyncIterator, Collection
from datetime import timedelta
from decimal import Decimal
from time import monotonic
from typing import Any

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import add_user, events_of

from zheka.core.enums import EventType
from zheka.core.errors import InvalidRequest, TooManyRequests
from zheka.core.ids import HouseId
from zheka.core.services.events import EventsService
from zheka.core.services.house_point import (
    GEOCODER_FAILED,
    NO_BUILDING,
    HousePointService,
    directory_region,
    normalized_building,
    normalized_street,
)
from zheka.infra import nominatim
from zheka.infra.database.models import House
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import ADD_HOUSE_LOCK, HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.tables.houses import houses_table
from zheka.infra.nominatim import (
    SLOT_KEY,
    USER_AGENT,
    GeocoderUnavailable,
    NominatimClient,
    ReverseAddress,
    parse_reverse,
)
from zheka.infra.quota import (
    HOUSE_ADD_CALLS,
    HOUSE_LOOKUP_CALLS,
    HouseAddQuota,
    HouseLookupQuota,
)

STREET = "улица Картографов"
REGION = "Картовая область"
LIGOVSKY: dict[str, Any] = {
    "category": "building",
    "address": {
        "house_number": "68",
        "road": "Лиговский проспект",
        "city_district": "округ Лиговка-Ямская",
        "city": "Санкт-Петербург",
        "state": "Санкт-Петербург",
        "ISO3166-2-lvl4": "RU-SPE",
        "region": "Северо-Западный федеральный округ",
        "postcode": "191040",
        "country": "Россия",
        "country_code": "ru",
    },
}


class FakeGeocoder:
    def __init__(self, answer: ReverseAddress | Exception | None) -> None:
        self.answer = answer
        self.calls = 0

    async def reverse(self, lat: float, lon: float) -> ReverseAddress | None:  # noqa: ARG002
        self.calls += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _address(
    building: str = "5",
    iso_region: str | None = None,
    region: str = REGION,
) -> ReverseAddress:
    return ReverseAddress(
        region=region,
        city="Картоград",
        street=STREET,
        building=building,
        iso_region=iso_region,
    )


def _service(
    session: AsyncSession,
    geocoder: FakeGeocoder,
    *,
    houses: HousesRepo | None = None,
    quota: HouseAddQuota | None = None,
    lookups: HouseLookupQuota | None = None,
) -> HousePointService:
    return HousePointService(
        houses or HousesRepo(session),
        OrgsRepo(session),
        geocoder,
        quota or HouseAddQuota(),
        EventsService(EventsRepo(session)),
        lookups or HouseLookupQuota(),
    )


def _spot() -> tuple[float, float]:
    return -50 - secrets.randbelow(10_000) / 1000, -120 - secrets.randbelow(
        10_000,
    ) / 1000


async def _house(
    session: AsyncSession,
    lat: float | None,
    lon: float | None,
    building: str = "1",
    region: str = REGION,
) -> HouseId:
    house = House(
        region=region,
        city="Картоград",
        street=STREET,
        building=building,
        lat=None if lat is None else Decimal(str(round(lat, 6))),
        lon=None if lon is None else Decimal(str(round(lon, 6))),
        chat_binding_code=secrets.token_hex(4),
        timezone="Europe/Moscow",
    )
    session.add(house)
    await session.flush()
    return house.id


async def _count_houses_at(session: AsyncSession, lat: float, lon: float) -> int:
    stmt = (
        select(func.count())
        .select_from(houses_table)
        .where(
            houses_table.c.lat.between(
                Decimal(str(lat - 0.01)),
                Decimal(str(lat + 0.01)),
            ),
            houses_table.c.lon.between(
                Decimal(str(lon - 0.01)),
                Decimal(str(lon + 0.01)),
            ),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10 к.1", "10к1"),
        ("10 к1", "10к1"),
        ("1 корп. 1 литера А", "1к1"),
        ("1 корпус 1 лит. А", "1к1"),
        ("1 с.1", "1с1"),
        ("1 строение 1", "1с1"),
        ("64 литера А", "64"),
        ("44 литА", "44"),
        ("70 корп. 2 литера Ж", "70к2литж"),
        ("70 к2 литЖ", "70к2литж"),
        ("9А литера Б", "9алитб"),
        ("9А литБ", "9алитб"),
        ("20А", "20а"),
    ],
)
def test_building_numbers_normalize_to_one_form(raw: str, expected: str) -> None:
    assert normalized_building(raw) == expected


def test_a_reverse_answer_without_a_house_number_is_no_address() -> None:
    address = {"road": "Ленинский проспект", "city": "Москва", "country_code": "ru"}
    assert parse_reverse({"address": address}) is None


def test_a_reverse_answer_keeps_region_code_and_town() -> None:
    data: dict[str, Any] = {
        "address": {
            "house_number": "5",
            "road": "улица Ленина",
            "town": "Верхняя Пышма",
            "state": "Свердловская область",
            "ISO3166-2-lvl4": "RU-SVE",
            "country_code": "ru",
        },
    }
    found = parse_reverse(data)
    assert found == ReverseAddress(
        region="Свердловская область",
        city="Верхняя Пышма",
        street="улица Ленина",
        building="5",
        iso_region="RU-SVE",
    )


async def test_a_tap_next_to_a_known_house_picks_it_without_the_geocoder(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    house_id = await _house(session, lat + 0.0001, lon)
    geocoder = FakeGeocoder(_address())

    found = await _service(session, geocoder).at(await add_user(session), lat, lon)

    assert found.house is not None
    assert found.house.house.id == house_id
    assert geocoder.calls == 0
    events = await events_of(session, EventType.HOUSE_SEARCH)
    assert [
        (event.payload["found"], type(event.payload["found"])) for event in events
    ] == [(1, int)]


async def test_a_geocoded_address_matches_a_nearby_house_by_street_and_building(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    house_id = await _house(session, lat + 120 / 111_320, lon, building="10 к.1")
    geocoder = FakeGeocoder(_address(building="10 к1"))

    found = await _service(session, geocoder).at(await add_user(session), lat, lon)

    assert found.house is not None
    assert found.house.house.id == house_id


async def test_an_unknown_address_is_offered_but_not_created_by_a_look(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()

    found = await _service(session, FakeGeocoder(_address())).at(
        await add_user(session),
        lat,
        lon,
    )

    assert found.house is None
    assert found.address == _address()
    assert await _count_houses_at(session, lat, lon) == 0


async def test_adding_creates_a_house_marked_as_added_by_a_resident_in_its_region_zone(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    geocoder = FakeGeocoder(_address(iso_region="RU-SVE"))

    found = await _service(session, geocoder).add(await add_user(session), lat, lon)

    house = found.house
    assert house.timezone == "Asia/Yekaterinburg"
    assert house.added_by_resident is True
    assert house.org_id is None
    assert found.is_connected is False
    events = await events_of(session, EventType.HOUSE_ADDED)
    assert house.id in {event.payload["house_id"] for event in events}


async def test_adding_where_a_house_already_is_returns_it(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    house_id = await _house(session, lat, lon)

    found = await _service(session, FakeGeocoder(_address())).add(
        await add_user(session),
        lat,
        lon,
    )

    assert found.house.id == house_id
    assert await _count_houses_at(session, lat, lon) == 1


async def test_adding_without_a_house_number_is_refused(session: AsyncSession) -> None:
    lat, lon = _spot()

    with pytest.raises(InvalidRequest, match=NO_BUILDING):
        await _service(session, FakeGeocoder(None)).add(
            await add_user(session),
            lat,
            lon,
        )


async def test_a_geocoder_failure_is_reported_and_adding_is_refused(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    user_id = await add_user(session)
    service = _service(session, FakeGeocoder(GeocoderUnavailable()))

    found = await service.at(user_id, lat, lon)

    assert found.geocoder_failed is True
    with pytest.raises(InvalidRequest, match=GEOCODER_FAILED):
        await service.add(user_id, lat, lon)


async def test_the_sixth_house_in_an_hour_is_refused(session: AsyncSession) -> None:
    user_id = await add_user(session)
    service = _service(session, FakeGeocoder(_address()))
    for _ in range(HOUSE_ADD_CALLS):
        await service.add(user_id, *_spot())

    with pytest.raises(TooManyRequests):
        await service.add(user_id, *_spot())


class RacedHousesRepo(HousesRepo):
    def __init__(self, session: AsyncSession, lat: float, lon: float) -> None:
        super().__init__(session)
        self.lat = lat
        self.lon = lon

    async def lock_adding(self) -> None:
        await _house(self._session, self.lat + 0.0005, self.lon, building="5")
        await super().lock_adding()


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.expires: dict[str, float] = {}

    async def get(self, key: str) -> Any:
        if self.expires.get(key, float("inf")) <= monotonic():
            self.values.pop(key, None)
        return self.values.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        *,
        ex: timedelta | None = None,  # noqa: ARG002
        px: int | None = None,
        nx: bool = False,
    ) -> bool:
        if nx and await self.get(key) is not None:
            return False
        self.values[key] = value
        if px is not None:
            self.expires[key] = monotonic() + px / 1000
        return True


class BrokenRedis(FakeRedis):
    async def get(self, key: str) -> Any:  # noqa: ARG002
        raise RedisConnectionError


class Upstream:
    def __init__(self, http: aiohttp.ClientSession) -> None:
        self.http = http
        self.hits: list[float] = []
        self.agents: list[str] = []
        self.status = 200
        self.body = json.dumps(LIGOVSKY)

    async def handle(self, request: web.Request) -> web.StreamResponse:
        self.hits.append(monotonic())
        self.agents.append(request.headers["User-Agent"])
        return web.Response(
            text=self.body,
            status=self.status,
            content_type="application/json",
        )

    def client(self, redis: FakeRedis) -> NominatimClient:
        return NominatimClient(self.http, redis)  # type: ignore[arg-type]


@pytest.fixture
async def upstream(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Upstream]:
    async with aiohttp.ClientSession() as http:
        served = Upstream(http)
        app = web.Application()
        app.router.add_get("/reverse", served.handle)
        async with TestServer(app) as server:
            monkeypatch.setattr(
                nominatim,
                "REVERSE_URL",
                str(server.make_url("/reverse")),
            )
            yield served


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ленинский проспект (дублёр)", "ленинский проспект"),
        ("улица  Лёни Голикова", "улица лени голикова"),
    ],
)
def test_street_names_normalize_to_one_form(raw: str, expected: str) -> None:
    assert normalized_street(raw) == expected


@pytest.mark.parametrize(
    ("region", "known", "expected"),
    [
        ("Татарстан", {"Москва", "Республика Татарстан"}, "Республика Татарстан"),
        ("Москва", {"Москва", "Московская область"}, "Москва"),
        ("Московская область", {"Москва"}, "Московская область"),
        ("Алтай", {"Алтайский край"}, "Алтай"),
    ],
)
def test_a_region_takes_the_directory_name_of_the_same_region(
    region: str,
    known: Collection[str],
    expected: str,
) -> None:
    assert directory_region(region, known) == expected


def test_an_answer_outside_russia_is_no_address() -> None:
    data: dict[str, Any] = {
        "address": {
            "house_number": "5",
            "road": "проспект Независимости",
            "city": "Минск",
            "state": "Минск",
            "country_code": "by",
        },
    }

    assert parse_reverse(data) is None


async def test_a_geocoded_address_matches_a_directory_house_with_the_default_litera(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    house_id = await _house(
        session,
        lat + 120 / 111_320,
        lon,
        building="20 литера А",
    )
    geocoder = FakeGeocoder(_address(building="20"))

    found = await _service(session, geocoder).at(await add_user(session), lat, lon)

    assert found.house is not None
    assert found.house.house.id == house_id


async def test_a_geocoded_address_matches_a_directory_house_without_coordinates(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    house_id = await _house(session, None, None, building="7 к.2")
    geocoder = FakeGeocoder(_address(building="7 к2"))

    found = await _service(session, geocoder).at(await add_user(session), lat, lon)

    assert found.house is not None
    assert found.house.house.id == house_id


async def test_an_added_house_takes_the_directory_name_of_its_region(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    await _house(session, *_spot(), building="1", region="Республика Картовия")
    geocoder = FakeGeocoder(_address(region="Картовия"))

    found = await _service(session, geocoder).add(await add_user(session), lat, lon)

    assert found.house.region == "Республика Картовия"


async def test_lookups_past_the_quota_are_refused_before_the_geocoder(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    user_id = await add_user(session)
    lookups = HouseLookupQuota()
    for _ in range(HOUSE_LOOKUP_CALLS):
        lookups.take(user_id)
    geocoder = FakeGeocoder(_address())

    with pytest.raises(TooManyRequests):
        await _service(session, geocoder, lookups=lookups).at(user_id, lat, lon)
    assert geocoder.calls == 0


async def test_returning_a_known_house_uses_no_new_house_slot(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    user_id = await add_user(session)
    house_id = await _house(session, lat, lon)
    quota = HouseAddQuota()
    for _ in range(HOUSE_ADD_CALLS):
        quota.take(user_id)

    found = await _service(session, FakeGeocoder(_address()), quota=quota).add(
        user_id,
        lat,
        lon,
    )

    assert found.house.id == house_id


async def test_a_twin_added_while_waiting_for_the_lock_is_returned(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    service = _service(
        session,
        FakeGeocoder(_address()),
        houses=RacedHousesRepo(session, lat, lon),
    )

    found = await service.add(await add_user(session), lat, lon)

    assert found.house.added_by_resident is False
    assert await _count_houses_at(session, lat, lon) == 1


async def test_adding_holds_the_house_lock_until_the_transaction_ends(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()

    await _service(session, FakeGeocoder(_address())).add(
        await add_user(session),
        lat,
        lon,
    )

    stmt = text(
        "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory'"
        " AND objid = :key AND objsubid = 1 AND pid = pg_backend_pid()",
    )
    assert (await session.execute(stmt, {"key": ADD_HOUSE_LOCK})).scalar_one() == 1


async def test_a_point_is_looked_up_once_for_every_worker(upstream: Upstream) -> None:
    redis = FakeRedis()

    first = await upstream.client(redis).reverse(59.922503, 30.3557788)
    second = await upstream.client(redis).reverse(59.922503, 30.3557788)

    assert (
        first
        == second
        == ReverseAddress(
            region="Санкт-Петербург",
            city="Санкт-Петербург",
            street="Лиговский проспект",
            building="68",
            iso_region="RU-SPE",
        )
    )
    assert upstream.agents == [USER_AGENT]


async def test_lookups_from_two_workers_are_a_slot_apart(
    upstream: Upstream,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(nominatim, "SLOT_MS", 300)
    redis = FakeRedis()

    await asyncio.gather(
        upstream.client(redis).reverse(59.9225, 30.3557),
        upstream.client(redis).reverse(59.9226, 30.3558),
    )

    first, second = upstream.hits
    assert second - first >= 0.25


async def test_a_lookup_gives_up_while_the_slot_stays_taken(
    upstream: Upstream,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(nominatim, "SLOT_WAIT", 0.2)
    redis = FakeRedis()
    redis.values[SLOT_KEY] = 1

    with pytest.raises(GeocoderUnavailable):
        await asyncio.wait_for(upstream.client(redis).reverse(59.9225, 30.3557), 2)
    assert upstream.hits == []


@pytest.mark.parametrize(
    ("status", "body"),
    [(503, "{}"), (429, "{}"), (200, "<html>Bad Gateway</html>")],
)
async def test_a_failed_lookup_is_unavailable_and_not_cached(
    upstream: Upstream,
    status: int,
    body: str,
) -> None:
    redis = FakeRedis()
    upstream.status, upstream.body = status, body

    with pytest.raises(GeocoderUnavailable):
        await upstream.client(redis).reverse(59.9225, 30.3557)
    redis.expires[SLOT_KEY] = 0
    upstream.status, upstream.body = 200, json.dumps(LIGOVSKY)

    assert await upstream.client(redis).reverse(59.9225, 30.3557) is not None
    assert len(upstream.hits) == 2


async def test_a_broken_redis_makes_the_geocoder_unavailable(
    upstream: Upstream,
) -> None:
    with pytest.raises(GeocoderUnavailable):
        await upstream.client(BrokenRedis()).reverse(59.9225, 30.3557)


async def test_a_tap_on_houses_at_one_point_always_picks_the_first_added(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    first = await _house(session, lat, lon, building="11 с.1")
    await _house(session, lat, lon, building="11 с.4")
    stmt = (
        houses_table.update()
        .where(houses_table.c.id == first)
        .values(building="11 строение 1")
    )
    await session.execute(stmt)
    geocoder = FakeGeocoder(_address())

    found = await _service(session, geocoder).at(await add_user(session), lat, lon)

    assert found.house is not None
    assert found.house.house.id == first


async def test_an_address_of_two_unplaced_houses_picks_the_first_added(
    session: AsyncSession,
) -> None:
    lat, lon = _spot()
    first = await _house(session, None, None, building="5")
    await _house(session, None, None, building="5")
    stmt = (
        houses_table.update()
        .where(houses_table.c.id == first)
        .values(street=f"{STREET} (дублер)")
    )
    await session.execute(stmt)

    found = await _service(session, FakeGeocoder(_address())).at(
        await add_user(session),
        lat,
        lon,
    )

    assert found.house is not None
    assert found.house.house.id == first
