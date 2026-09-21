from dishka import BaseScope, Provider, Scope, provide

from zheka.config import YandexConfig
from zheka.infra.yandex import VisionClient, YandexClassifier


class YandexProvider(Provider):
    scope: BaseScope | None = Scope.APP

    vision_client = provide(VisionClient)

    @provide
    def classifier(self, config: YandexConfig) -> YandexClassifier:
        return YandexClassifier(config)
