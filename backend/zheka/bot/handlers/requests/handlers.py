from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput, MessageInput
from maxo.dialogs.widgets.kbd import Button, Select
from maxo.types import MessageCallback, MessageCreated, PhotoAttachment

from zheka.bot.middlewares.user import USER_KEY
from zheka.bot.states import NewRequest
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import CATEGORY_RULES, RequestCategory, RequestChannel
from zheka.core.ids import UserId
from zheka.core.models import User
from zheka.core.services.profile import ProfileService
from zheka.core.services.requests import MAX_PHOTOS

SENT_TEXT = "Принял, оформляю"


def _user_id(dialog_manager: DialogManager) -> UserId:
    user: User = dialog_manager.middleware_data[USER_KEY]
    return UserId(user.id)


@inject
async def get_category(
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    **_: Any,
) -> dict[str, Any]:
    me = await profile_service.me(_user_id(dialog_manager))
    if not me.residencies:
        return {"address": None, "categories": []}

    # дом у жителя обычно один, а если их несколько - заявка идет в тот,
    # который он завел последним: выбор дома живет в мини-аппе
    residency = max(me.residencies, key=lambda item: item.resident.created_at)
    data = dialog_manager.dialog_data
    data["house_id"] = int(residency.house.id)
    data["flat_id"] = None if residency.flat is None else int(residency.flat.id)
    return {
        "address": residency.house.address,
        "categories": [
            {"id": category.value, "label": CATEGORY_RULES[category].label}
            for category in RequestCategory
        ],
    }


async def get_draft(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    data = dialog_manager.dialog_data
    category = data.get("category")
    return {
        "category": None
        if category is None
        else CATEGORY_RULES[RequestCategory(category)].label,
        "description": data.get("description", ""),
        "photos": len(data.get("photos", [])),
    }


async def get_sent(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    # окно рисует и житель сразу после нажатия, и задача, когда заявка готова:
    # номер приходит в start_data, до него его просто нет
    start_data = dialog_manager.start_data
    request_id = start_data.get("request_id") if isinstance(start_data, dict) else None
    return {"request_id": request_id}


async def on_category(
    _callback: MessageCallback,
    _select: Select[str],
    dialog_manager: DialogManager,
    category: str,
) -> None:
    dialog_manager.dialog_data["category"] = RequestCategory(category).value
    await dialog_manager.switch_to(NewRequest.description)


async def on_description(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    description: str,
) -> None:
    dialog_manager.dialog_data["description"] = description
    await dialog_manager.switch_to(NewRequest.photo)


async def on_photo(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
) -> None:
    photos: list[str] = dialog_manager.dialog_data.setdefault("photos", [])
    for attach in update.message.body.attachments or []:
        if isinstance(attach, PhotoAttachment) and len(photos) < MAX_PHOTOS:
            photos.append(attach.payload.url)


@inject
async def on_send(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    publisher: FromDishka[TaskPublisher],
) -> None:
    # свой stack_id: задача заменит это же окно карточкой, а не откроет второе
    data = dialog_manager.dialog_data
    publisher.publish(
        TaskName.CREATE_BOT_REQUEST,
        user_id=int(_user_id(dialog_manager)),
        house_id=data["house_id"],
        flat_id=data.get("flat_id"),
        category=data["category"],
        description=data["description"],
        photo_urls=data.get("photos", []),
        channel=RequestChannel.BOT.value,
        stack_id=dialog_manager.current_stack().id,
    )
    await dialog_manager.switch_to(NewRequest.sent)
