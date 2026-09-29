from typing import Any

from dishka import STRICT_VALIDATION, AsyncContainer, Provider, make_async_container
from dishka.integrations.fastapi import FastapiProvider
from dishka.integrations.taskiq import TaskiqProvider
from maxo import Dispatcher
from maxo.dialogs import BgManagerFactory
from maxo.integrations.dishka import MaxoProvider

from zheka.bot import BotSetup
from zheka.config import Config
from zheka.di.broker import BrokerProvider
from zheka.di.config import ConfigProvider
from zheka.di.core.services import ServicesProvider
from zheka.di.database.repos import ReposProvider
from zheka.di.database.session import DbProvider
from zheka.di.max_bot import MaxBotProvider
from zheka.di.nominatim import NominatimProvider
from zheka.di.yandex import YandexProvider


def make_container(
    *extra_providers: Provider,
    config: Config,
    bot_setup: BotSetup | None = None,
) -> AsyncContainer:
    context: dict[Any, Any] = {Config: config}
    if bot_setup is not None:
        context |= {
            Dispatcher: bot_setup.dp,
            BgManagerFactory: bot_setup.bg_manager_factory,
        }
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
        NominatimProvider(),
        *extra_providers,
        context=context,
        validation_settings=STRICT_VALIDATION,
    )
