from typing import NewType, cast

from dishka import BaseScope, Provider, Scope, provide
from taskiq import AsyncBroker, ScheduleSource, TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListRedisScheduleSource, RedisStreamBroker

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


def make_broker(config: RedisConfig) -> RedisStreamBroker:
    # xread_block меньше socket_timeout, иначе redis-py обрывает чтение
    # раньше, чем брокер вернёт пустой ответ
    return RedisStreamBroker(
        url=config.url,
        queue_name="zheka-tasks",
        consumer_group_name="zheka-tasks",
        xread_block=30_000,
        socket_connect_timeout=30,
        socket_timeout=60,
    )


def make_schedule_source(config: RedisConfig) -> ListRedisScheduleSource:
    return ListRedisScheduleSource(url=config.url, prefix="zheka-schedule")
