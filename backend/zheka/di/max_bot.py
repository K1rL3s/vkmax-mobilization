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

    bg_manager_factory = from_context(BgManagerFactory)

    max_sender = provide(MaxSender)

    @provide(override=True)
    async def bot(self, config: MaxConfig) -> AsyncIterable[Bot]:
        defaults = BotDefaults(text_format=TextFormat.HTML, disable_link_preview=True)
        bot = Bot(token=config.token, defaults=defaults)
        async with bot:
            yield bot
