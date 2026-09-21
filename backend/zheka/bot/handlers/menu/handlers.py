from typing import Any

from maxo import Bot
from maxo.dialogs import DialogManager
from maxo.omit import is_defined

from zheka.bot.dialog_data import MenuData


async def get_menu(bot: Bot, dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    # ни одного сервиса: с этого окна перезапускает роутер ошибок, живущий
    # снаружи dishka. web_app у OpenAppButton - username бота, а не url
    username = bot.state.info.username
    return {
        "bot_username": username if is_defined(username) else None,
        "notice": MenuData.load_start(dialog_manager).notice,
    }
