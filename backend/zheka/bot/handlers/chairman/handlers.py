from html import escape
from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback

from zheka.bot.cards import back_to_menu
from zheka.bot.dialog_data import ChairmanData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.core.errors import ZhekaError
from zheka.core.services.chairman import ChairmanService

ACCEPTED = "🏛 Вы председатель совета дома {address}"
DECLINED = "👌 Вы отказались от роли председателя, {name} об этом узнает"


async def on_start(_start_data: Any, dialog_manager: DialogManager) -> None:
    ChairmanData.load_start(dialog_manager).dump(dialog_manager)


async def get_offer(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    return {"offer": ChairmanData.load(dialog_manager).offer}


@inject
async def on_accept(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    chairman_service: FromDishka[ChairmanService],
) -> None:
    data = ChairmanData.load(dialog_manager)
    try:
        offer = await chairman_service.accept(
            dialog_user_id(dialog_manager),
            data.code,
        )
    except ZhekaError as error:
        await back_to_menu(dialog_manager, str(error))
        return
    await back_to_menu(dialog_manager, ACCEPTED.format(address=escape(offer.address)))


@inject
async def on_decline(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    chairman_service: FromDishka[ChairmanService],
) -> None:
    data = ChairmanData.load(dialog_manager)
    try:
        offer = await chairman_service.decline(
            dialog_user_id(dialog_manager),
            data.code,
        )
    except ZhekaError as error:
        await back_to_menu(dialog_manager, str(error))
        return
    await back_to_menu(dialog_manager, DECLINED.format(name=escape(offer.from_name)))
