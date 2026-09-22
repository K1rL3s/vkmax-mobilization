from html import escape
from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput, MessageInput
from maxo.dialogs.widgets.kbd import Button, Select
from maxo.types import MessageCallback, MessageCreated, PhotoAttachment

from zheka.bot.dialog_data import NewRequestData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import NewRequest
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import CATEGORY_RULES, RequestCategory, RequestChannel
from zheka.core.services.profile import ProfileService
from zheka.core.services.requests import MAX_PHOTOS

SENT_TEXT = "⏳ Принял, оформляю"


@inject
async def get_category(
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    **_: Any,
) -> dict[str, Any]:
    me = await profile_service.me(dialog_user_id(dialog_manager))
    if not me.residencies:
        return {"address": None, "connected": False, "categories": []}

    residency = max(me.residencies, key=lambda item: item.resident.created_at)
    address = escape(residency.house.address)
    if not residency.is_connected:
        return {"address": address, "connected": False, "categories": []}
    with NewRequestData.proxy(dialog_manager) as data:
        data.house_id = residency.house.id
        data.flat_id = None if residency.flat is None else residency.flat.id
    return {
        "address": address,
        "connected": True,
        "categories": [
            {"id": category.value, "label": CATEGORY_RULES[category].caption}
            for category in RequestCategory
        ],
    }


async def get_draft(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    data = NewRequestData.load(dialog_manager)
    return {
        "category": (
            None if data.category is None else CATEGORY_RULES[data.category].caption
        ),
        "description": escape(data.description),
        "photos": len(data.photos),
    }


async def get_sent(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    return {"request_id": NewRequestData.load_start(dialog_manager).request_id}


async def on_category(
    _callback: MessageCallback,
    _select: Select[str],
    dialog_manager: DialogManager,
    category: str,
) -> None:
    with NewRequestData.proxy(dialog_manager) as data:
        data.category = RequestCategory(category)
    await dialog_manager.switch_to(NewRequest.description)


async def on_description(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    description: str,
) -> None:
    with NewRequestData.proxy(dialog_manager) as data:
        data.description = description
    await dialog_manager.switch_to(NewRequest.photo)


async def on_photo(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
) -> None:
    with NewRequestData.proxy(dialog_manager) as data:
        for attach in update.message.body.attachments or []:
            if isinstance(attach, PhotoAttachment) and len(data.photos) < MAX_PHOTOS:
                data.photos.append(attach.payload.url)


@inject
async def on_send(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    publisher: FromDishka[TaskPublisher],
) -> None:
    data = NewRequestData.load(dialog_manager)
    publisher.publish(
        TaskName.CREATE_BOT_REQUEST,
        user_id=dialog_user_id(dialog_manager),
        house_id=data.house_id,
        flat_id=data.flat_id,
        category=data.category,
        description=data.description,
        photo_urls=data.photos,
        channel=RequestChannel.BOT.value,
        stack_id=dialog_manager.current_stack().id,
    )
    await dialog_manager.switch_to(NewRequest.sent)
