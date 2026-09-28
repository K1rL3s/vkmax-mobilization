from collections.abc import AsyncIterable

from dishka import BaseScope, Provider, Scope, provide
from redis.asyncio import Redis

from zheka.config import RedisConfig
from zheka.core.services.house_point import Geocoder
from zheka.infra.nominatim import TIMEOUT, NominatimClient


class NominatimProvider(Provider):
    scope: BaseScope | None = Scope.APP

    geocoder = provide(NominatimClient, provides=Geocoder, scope=Scope.APP)

    @provide
    async def redis(self, config: RedisConfig) -> AsyncIterable[Redis]:
        client = Redis.from_url(config.url, socket_timeout=TIMEOUT)
        yield client
        await client.aclose()
