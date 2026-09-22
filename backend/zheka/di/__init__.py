from typing import Any

from dishka import STRICT_VALIDATION, AsyncContainer, Provider, make_async_container
from dishka.integrations.fastapi import FastapiProvider
from dishka.integrations.taskiq import TaskiqProvider
from maxo.integrations.dishka import MaxoProvider

from zheka.config import Config
from zheka.di.broker import BrokerProvider
from zheka.di.config import ConfigProvider
from zheka.di.core.services import ServicesProvider
from zheka.di.database.repos import ReposProvider
from zheka.di.database.session import DbProvider
from zheka.di.max_bot import MaxBotProvider
from zheka.di.yandex import YandexProvider


def make_container(
    *extra_providers: Provider,
    config: Config,
    context: dict[Any, Any] | None = None,
) -> AsyncContainer:
    return make_async_container(
        FastapiProvider(),
        TaskiqProvider(),
        MaxoProvider(),
        ConfigProvider(),
        DbProvider(),
        ReposProvider(),
        ServicesProvider(),
        MaxBotProvider(),
        BrokerProvider(),
        YandexProvider(),
        *extra_providers,
        context={**(context or {}), Config: config},
        validation_settings=STRICT_VALIDATION,
    )
