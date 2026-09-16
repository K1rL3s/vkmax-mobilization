from collections.abc import AsyncIterable

from dishka import BaseScope, Provider, Scope, provide
from maxo import Bot
from maxo.bot.defaults import BotDefaults
from maxo.enums import TextFormat

from zheka.config import MaxConfig
from zheka.infra.max import MaxSender


class MaxBotProvider(Provider):
    scope: BaseScope | None = Scope.APP

    max_sender = provide(MaxSender)

    # override=True: maxo's own MaxoProvider declares Bot via from_context,
    # expecting the app to inject a ready instance - we build ours from the
    # token instead, so ours is the real provider and that one is unused
    @provide(override=True)
    async def bot(self, config: MaxConfig) -> AsyncIterable[Bot]:
        bot = Bot(
            token=config.token,
            defaults=BotDefaults(text_format=TextFormat.HTML),
        )
        async with bot:
            yield bot
