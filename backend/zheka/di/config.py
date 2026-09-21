from dishka import BaseScope, Provider, Scope, from_context, provide

from zheka.config import (
    Config,
    DbConfig,
    DeeplinksConfig,
    FilesConfig,
    MaxConfig,
    RedisConfig,
    YandexConfig,
)


class ConfigProvider(Provider):
    scope: BaseScope | None = Scope.APP

    config = from_context(Config)

    @provide
    def db(self, config: Config) -> DbConfig:
        return config.db

    @provide
    def redis(self, config: Config) -> RedisConfig:
        return config.redis

    @provide
    def max(self, config: Config) -> MaxConfig:
        return config.max

    @provide
    def files(self, config: Config) -> FilesConfig:
        return config.files

    @provide
    def deeplinks(self, config: Config) -> DeeplinksConfig:
        return config.deeplinks

    @provide
    def yandex(self, config: Config) -> YandexConfig:
        return config.yandex
