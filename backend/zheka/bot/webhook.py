from maxo import Bot, Dispatcher
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
