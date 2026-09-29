import asyncio
import json
from datetime import timedelta
from time import monotonic
from typing import Any

import aiohttp
from redis.asyncio import Redis
from redis.exceptions import RedisError

from zheka.base import ZhekaType

REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "zheka-kommunalkin/1.0 (+https://vkmax.k1rles.ru)"
TIMEOUT = 3.0
SLOT_KEY = "nominatim:slot"
SLOT_MS = 1000
SLOT_WAIT = 1.5
SLOT_POLL = 0.1
CACHE_KEY = "nominatim:reverse"
CACHE_TTL = timedelta(days=30)
CACHE_DIGITS = 5
COUNTRY_CODE = "ru"
_CITY_KEYS = ("city", "town", "village", "hamlet")
_STREET_KEYS = ("road", "pedestrian", "residential", "square")


class GeocoderUnavailable(Exception):
    pass


class ReverseAddress(ZhekaType):
    region: str
    city: str
    street: str
    building: str
    iso_region: str | None = None

    @property
    def address(self) -> str:
        return f"{self.city}, {self.street}, {self.building}"


def parse_reverse(data: dict[str, Any]) -> ReverseAddress | None:
    address = data.get("address") or {}
    if address.get("country_code") != COUNTRY_CODE:
        return None
    building = address.get("house_number")
    city = next((address[key] for key in _CITY_KEYS if address.get(key)), None)
    street = next((address[key] for key in _STREET_KEYS if address.get(key)), None)
    if not building or not city or not street:
        return None
    return ReverseAddress(
        region=address.get("state") or city,
        city=city,
        street=street,
        building=building,
        iso_region=address.get("ISO3166-2-lvl4"),
    )


class NominatimClient:
    __slots__ = ("_redis", "_session")

    def __init__(self, session: aiohttp.ClientSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis

    async def reverse(self, lat: float, lon: float) -> ReverseAddress | None:
        point = (f"{lat:.{CACHE_DIGITS}f}", f"{lon:.{CACHE_DIGITS}f}")
        key = f"{CACHE_KEY}:{point[0]}:{point[1]}"
        try:
            cached = await self._redis.get(key)
            if cached is None:
                cached = json.dumps(await self._fetch(*point))
                await self._redis.set(key, cached, ex=CACHE_TTL)
        except RedisError as error:
            raise GeocoderUnavailable from error
        return parse_reverse(json.loads(cached))

    async def _fetch(self, lat: str, lon: str) -> dict[str, Any]:
        deadline = monotonic() + SLOT_WAIT
        while not await self._redis.set(SLOT_KEY, 1, nx=True, px=SLOT_MS):
            if monotonic() >= deadline:
                raise GeocoderUnavailable
            await asyncio.sleep(SLOT_POLL)
        try:
            async with self._session.get(
                REVERSE_URL,
                params={
                    "format": "jsonv2",
                    "lat": lat,
                    "lon": lon,
                    "zoom": "18",
                    "addressdetails": "1",
                    "accept-language": "ru",
                },
                headers={"User-Agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                if not response.ok:
                    raise GeocoderUnavailable(response.status)
                data: dict[str, Any] = await response.json(content_type=None)
                return data
        except (aiohttp.ClientError, TimeoutError, ValueError) as error:
            raise GeocoderUnavailable from error
