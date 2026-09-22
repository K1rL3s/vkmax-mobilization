from typing import Any

from maxo import Bot

from zheka.bot.cards import web_app_name


async def get_menu(bot: Bot, **_: Any) -> dict[str, Any]:
    return {"bot_username": web_app_name(bot)}
