from collections.abc import AsyncIterable

import aiohttp
from dishka import BaseScope, Provider, Scope, provide

from zheka.infra.yandex import (
    SpeechClient,
    VisionClient,
    YandexClassifier,
    YandexQuota,
)


class YandexProvider(Provider):
    scope: BaseScope | None = Scope.APP

    vision_client = provide(VisionClient)
    classifier = provide(YandexClassifier)
    quota = provide(YandexQuota)
    speech_client = provide(SpeechClient)

    @provide
    async def http_session(self) -> AsyncIterable[aiohttp.ClientSession]:
        async with aiohttp.ClientSession() as session:
            yield session
