from dishka import BaseScope, Provider, Scope, provide

from zheka.infra.yandex import VisionClient


class YandexProvider(Provider):
    scope: BaseScope | None = Scope.APP

    vision_client = provide(VisionClient)
