from collections.abc import AsyncIterable

from dishka import BaseScope, Provider, Scope, from_context, provide
from maxo import Bot
from maxo.bot.defaults import BotDefaults
from maxo.dialogs import BgManagerFactory
from maxo.enums import TextFormat

from zheka.config import MaxConfig
from zheka.infra.max import MaxSender


class MaxBotProvider(Provider):
    scope: BaseScope | None = Scope.APP

    # ту самую, что вернул setup_dialogs, а не второй BgManagerFactoryImpl(dp)
    bg_manager_factory = from_context(BgManagerFactory)

    max_sender = provide(MaxSender)

    # MaxoProvider ждет Bot из контекста, а мы собираем его из токена
    @provide(override=True)
    async def bot(self, config: MaxConfig) -> AsyncIterable[Bot]:
        bot = Bot(token=config.token, defaults=BotDefaults(text_format=TextFormat.HTML))
        async with bot:
            yield bot
