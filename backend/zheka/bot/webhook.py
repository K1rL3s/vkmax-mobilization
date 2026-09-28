from maxo import Bot, Dispatcher
from maxo.routing.utils import collect_used_updates
from maxo.transport.webhook.adapters.fastapi import FastApiWebAdapter
from maxo.transport.webhook.engines import SimpleEngine
from maxo.transport.webhook.routing import StaticRouting
from maxo.transport.webhook.security import Security, StaticSecretToken

from zheka.config import MaxConfig


def make_engine(dp: Dispatcher, bot: Bot, config: MaxConfig) -> SimpleEngine:
    if not config.webhook_url:
        raise ValueError("Вебхуку нужен MAX_WEBHOOK_URL")
    if not config.secret_token:
        raise ValueError("Вебхуку нужен MAX_SECRET_TOKEN")

    return SimpleEngine(
        dp,
        bot,
        web_adapter=FastApiWebAdapter(),
        routing=StaticRouting(url=config.webhook_url),
        security=Security(secret_token=StaticSecretToken(config.secret_token)),
        handle_in_background=True,
    )


async def restore_webhook(engine: SimpleEngine) -> bool:
    url = engine.routing.webhook_point(engine.bot)
    result = await engine.bot.get_subscriptions()
    if any(subscription.url == url for subscription in result.subscriptions):
        return False
    await engine.set_webhook(
        update_types=list(collect_used_updates(engine.dispatcher)),
    )
    return True
