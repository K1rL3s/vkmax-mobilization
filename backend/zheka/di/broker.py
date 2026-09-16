from typing import NewType, cast

from dishka import BaseScope, Provider, Scope, provide
from taskiq import AsyncBroker, ScheduleSource, TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListQueueBroker, ListRedisScheduleSource

from zheka.config import RedisConfig

ZhekaBroker = NewType("ZhekaBroker", AsyncBroker)
ZhekaScheduleSource = NewType("ZhekaScheduleSource", ScheduleSource)


class BrokerProvider(Provider):
    scope: BaseScope | None = Scope.APP

    @provide
    def broker(self, config: RedisConfig) -> ZhekaBroker:
        return cast(ZhekaBroker, make_broker(config))

    @provide
    def schedule_source(self, config: RedisConfig) -> ZhekaScheduleSource:
        return cast(ZhekaScheduleSource, make_schedule_source(config))

    @provide
    def scheduler(
        self,
        broker: ZhekaBroker,
        schedule_source: ZhekaScheduleSource,
    ) -> TaskiqScheduler:
        return TaskiqScheduler(
            broker=broker,
            sources=[schedule_source, LabelScheduleSource(broker)],
        )


def make_broker(config: RedisConfig) -> ListQueueBroker:
    return ListQueueBroker(url=config.url, queue_name="zheka-tasks")


def make_schedule_source(config: RedisConfig) -> ListRedisScheduleSource:
    return ListRedisScheduleSource(url=config.url, prefix="zheka-schedule")
