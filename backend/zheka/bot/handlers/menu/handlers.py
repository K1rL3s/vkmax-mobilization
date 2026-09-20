from typing import Any

from maxo import Bot
from maxo.dialogs import DialogManager
from maxo.omit import is_defined


async def get_menu(
    bot: Bot,
    dialog_manager: DialogManager,
    **_: Any,
) -> dict[str, Any]:
    # ни одного сервиса: с этого окна перезапускает роутер ошибок, а он живет
    # снаружи контейнера dishka, и окно обязано рисоваться без запроса.
    # web_app у OpenAppButton - это username бота, а не url, поэтому ссылка на
    # мини-апп берется у самого бота, а не из второго источника правды в конфиге
    username = bot.state.info.username
    start_data = dialog_manager.start_data
    notice = start_data.get("notice") if isinstance(start_data, dict) else None
    return {
        "bot_username": username if is_defined(username) else None,
        "notice": notice,
    }
