from dishka import BaseScope, Provider, Scope, from_context, provide

from zheka.config import ApiConfig, Config, DbConfig, LogConfig, MaxConfig, RedisConfig


class ConfigProvider(Provider):
    scope: BaseScope | None = Scope.APP

    config = from_context(Config)

    @provide
    def log(self, config: Config) -> LogConfig:
        return config.log

    @provide
    def api(self, config: Config) -> ApiConfig:
        return config.api

    @provide
    def db(self, config: Config) -> DbConfig:
        return config.db

    @provide
    def redis(self, config: Config) -> RedisConfig:
        return config.redis

    @provide
    def max(self, config: Config) -> MaxConfig:
        return config.max
