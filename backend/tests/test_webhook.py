from datetime import UTC, datetime
from typing import Any, cast

from maxo import Bot, Dispatcher
from maxo.omit import Omittable
from maxo.routing.utils import collect_used_updates
from maxo.types.get_subscriptions_result import GetSubscriptionsResult
from maxo.types.subscription import Subscription

from zheka.bot.webhook import make_engine, restore_webhook
from zheka.config import BotMode, MaxConfig

URL = "https://zheka.example/api/webhook"
CONFIG = MaxConfig(
    token="test-token",  # noqa: S106
    mode=BotMode.WEBHOOK,
    webhook_url=URL,
    secret_token="secret",  # noqa: S106
)


class SubscriptionsBot:
    def __init__(self, urls: list[str]) -> None:
        self.urls = urls
        self.subscribed: list[dict[str, Any]] = []

    async def get_subscriptions(self) -> GetSubscriptionsResult:
        return GetSubscriptionsResult(
            subscriptions=[
                Subscription(time=datetime.now(UTC), url=url) for url in self.urls
            ],
        )

    async def subscribe(
        self,
        url: str,
        secret: Omittable[str],
        update_types: Omittable[list[str]],
    ) -> None:
        self.subscribed.append(
            {"url": url, "secret": secret, "update_types": update_types},
        )


async def test_a_live_subscription_is_left_alone() -> None:
    bot = SubscriptionsBot([URL])

    restored = await restore_webhook(make_engine(Dispatcher(), cast(Bot, bot), CONFIG))

    assert not restored
    assert bot.subscribed == []


async def test_a_dropped_subscription_is_registered_again_with_the_secret() -> None:
    bot = SubscriptionsBot(["https://other.example/hook"])
    dp = Dispatcher()

    restored = await restore_webhook(make_engine(dp, cast(Bot, bot), CONFIG))

    assert restored
    assert bot.subscribed == [
        {
            "url": URL,
            "secret": "secret",
            "update_types": list(collect_used_updates(dp)),
        },
    ]
