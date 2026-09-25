from typing import NewType

from dishka import BaseScope, Provider, Scope, provide
from taskiq import AsyncBroker
from taskiq_redis import RedisStreamBroker

from zheka.broker.publisher import TaskPublisher
from zheka.config import RedisConfig

ZhekaBroker = NewType("ZhekaBroker", AsyncBroker)


class BrokerProvider(Provider):
    scope: BaseScope | None = Scope.APP

    @provide
    def broker(self, config: RedisConfig) -> ZhekaBroker:
        return ZhekaBroker(make_broker(config))

    @provide(scope=Scope.REQUEST)
    def publisher(self, broker: ZhekaBroker) -> TaskPublisher:
        return TaskPublisher(broker)


def make_broker(config: RedisConfig) -> RedisStreamBroker:
    return RedisStreamBroker(
        url=config.url,
        queue_name="zheka-tasks",
        consumer_group_name="zheka-tasks",
        xread_block=30_000,
        socket_connect_timeout=30,
        socket_timeout=60,
    )
