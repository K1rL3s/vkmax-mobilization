from typing import NewType

from dishka import BaseScope, Provider, Scope, provide
from taskiq import AsyncBroker, ScheduleSource, TaskiqScheduler, async_shared_broker
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListRedisScheduleSource, RedisStreamBroker

from zheka.broker.publisher import TaskPublisher
from zheka.config import RedisConfig

ZhekaBroker = NewType("ZhekaBroker", AsyncBroker)
ZhekaScheduleSource = NewType("ZhekaScheduleSource", ScheduleSource)


class BrokerProvider(Provider):
    scope: BaseScope | None = Scope.APP

    @provide
    def broker(self, config: RedisConfig) -> ZhekaBroker:
        return ZhekaBroker(make_broker(config))

    @provide(scope=Scope.REQUEST)
    def publisher(self, broker: ZhekaBroker) -> TaskPublisher:
        return TaskPublisher(broker)

    @provide
    def schedule_source(self, config: RedisConfig) -> ZhekaScheduleSource:
        return ZhekaScheduleSource(
            ListRedisScheduleSource(url=config.url, prefix="zheka-schedule")
        )

    @provide
    def scheduler(
        self, broker: ZhekaBroker, schedule_source: ZhekaScheduleSource
    ) -> TaskiqScheduler:
        return TaskiqScheduler(
            broker=broker,
            sources=[schedule_source, LabelScheduleSource(async_shared_broker)],
        )


def make_broker(config: RedisConfig) -> RedisStreamBroker:
    return RedisStreamBroker(
        url=config.url,
        queue_name="zheka-tasks",
        consumer_group_name="zheka-tasks",
        xread_block=30_000,
        socket_connect_timeout=30,
        socket_timeout=60,
    )
