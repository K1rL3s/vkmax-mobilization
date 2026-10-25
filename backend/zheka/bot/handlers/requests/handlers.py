from html import escape
from typing import Any

from dishka import FromDishka
from maxo import Bot
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput, MessageInput
from maxo.dialogs.widgets.kbd import Button
from maxo.types import MessageCallback, MessageCreated

from zheka.bot.cards import app_payload, back_to_menu, refused, web_app_name
from zheka.bot.dialog_data import NewRequestData, transcript, voice_url
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import NewRequest
from zheka.bot.voice import publish_transcription
from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.danger import detect_danger
from zheka.core.deeplinks import request_app_path
from zheka.core.enums import (
    CANCEL_REASONS,
    CATEGORY_PLACES,
    CATEGORY_RULES,
    CancelReason,
    RequestCategory,
    RequestChannel,
    RequestPlace,
)
from zheka.core.errors import ZhekaError
from zheka.core.ids import HouseId, RequestId
from zheka.core.services.announcements import AnnouncementsService
from zheka.core.services.profile import ProfileService
from zheka.core.services.requests import NEIGHBOUR_DESCRIPTION, RequestsService
from zheka.core.texts import (
    MOMENT,
    OPEN_REQUEST,
    REQUEST_STATUS_LABELS,
    danger_warning,
    flats_count,
)

SENT_TEXT = "⏳ Принял, оформляю"
NOT_CREATED = "😔 Заявку не удалось оформить: {reason}"
NOT_CREATED_UNEXPECTED = "😔 Заявку не удалось оформить, попробуйте еще раз"
QUOTE_LIMIT = 200
NEIGHBOURS_TEXT = (
    "👥 Соседи уже сообщили: {category}, {flats}, статус: {status}\n\n"
    "Если у вас то же самое, нажмите «У меня тоже»"
)


@inject
async def get_category(
    dialog_manager: DialogManager,
    profile_service: FromDishka[ProfileService],
    **_: Any,
) -> dict[str, Any]:
    me = await profile_service.me(dialog_user_id(dialog_manager))
    residency = me.latest_residency
    danger = detect_danger(NewRequestData.load(dialog_manager).description)
    warning = (
        None
        if danger is None
        else danger_warning(danger.kind, None if residency is None else residency.org)
    )
    if residency is None:
        return {
            "address": None,
            "connected": False,
            "categories": [],
            "danger": warning,
        }

    address = escape(residency.house.address)
    if not residency.is_connected:
        return {
            "address": address,
            "connected": False,
            "categories": [],
            "danger": warning,
        }
    with NewRequestData.proxy(dialog_manager) as data:
        data.house_id = residency.house.id
        data.flat_id = None if residency.flat is None else residency.flat.id
        description = data.description
    if len(description) > QUOTE_LIMIT:
        description = f"{description[:QUOTE_LIMIT]}…"
    return {
        "address": address,
        "connected": True,
        "description": escape(description),
        "danger": warning,
        "categories": [
            {"id": category.value, "label": CATEGORY_RULES[category].caption}
            for category in RequestCategory
        ],
    }


async def get_draft(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    data = NewRequestData.load(dialog_manager)
    rule = None if data.category is None else CATEGORY_RULES[data.category]
    return {
        "category": None if rule is None else rule.caption,
        "owner_zone": (
            rule.owner_zone
            if rule is not None and data.place is RequestPlace.FLAT
            else None
        ),
        "description": escape(data.description),
        "attachments": len(data.photos) + len(data.videos),
        "videos": len(data.videos),
        "voice_pending": data.voice_pending,
        "voice_failed": data.voice_failed,
    }


async def get_sent(
    bot: Bot,
    dialog_manager: DialogManager,
    **_: Any,
) -> dict[str, Any]:
    data = NewRequestData.load_start(dialog_manager)
    return {
        "request_id": data.request_id,
        "joined": data.group_id is not None,
        "deadline": data.deadline,
        "error": data.error,
        "bot_username": web_app_name(bot),
        "request_payload": (
            None
            if data.request_id is None
            else app_payload(request_app_path(RequestId(data.request_id)))
        ),
    }


@inject
async def on_category(
    _callback: MessageCallback,
    _select: Any,
    dialog_manager: DialogManager,
    category: str,
    requests_service: FromDishka[RequestsService],
) -> None:
    chosen = RequestCategory(category)
    house_id = NewRequestData.load(dialog_manager).house_id
    offer = (
        None
        if house_id is None
        else await requests_service.neighbours(
            dialog_user_id(dialog_manager),
            HouseId(house_id),
            chosen,
        )
    )
    with NewRequestData.proxy(dialog_manager) as data:
        data.category = chosen
        data.place = CATEGORY_PLACES.get(chosen)
        data.group_id = None if offer is None else offer.group_id
        data.neighbours = (
            None
            if offer is None
            else NEIGHBOURS_TEXT.format(
                category=CATEGORY_RULES[chosen].caption,
                flats=flats_count(offer.flats_count),
                status=REQUEST_STATUS_LABELS[offer.status].lower(),
            )
        )
    if offer is not None:
        await dialog_manager.switch_to(NewRequest.neighbours)
        return
    await _after_category(dialog_manager)


async def on_description(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    description: str,
) -> None:
    await _describe(dialog_manager, description)


async def _describe(dialog_manager: DialogManager, description: str) -> None:
    with NewRequestData.proxy(dialog_manager) as data:
        data.description = description
        data.voice_failed = False
        data.voice_pending = False
    await dialog_manager.switch_to(NewRequest.attachments)


@inject
async def on_description_voice(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    publisher: FromDishka[TaskPublisher],
) -> None:
    text = transcript(update.message.body)
    if text:
        await _describe(dialog_manager, text)
        return
    with NewRequestData.proxy(dialog_manager) as data:
        data.voice_pending = True
        data.voice_failed = False
        draft = data.to_data()
    publish_transcription(
        publisher,
        dialog_user_id(dialog_manager),
        voice_url(update.message.body),
        draft,
        in_draft=True,
    )


async def on_attachment(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
) -> None:
    with NewRequestData.proxy(dialog_manager) as data:
        data.attach_attachments(update.message.body)


@inject
async def on_send(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    publisher: FromDishka[TaskPublisher],
) -> None:
    _publish(dialog_manager, publisher, None)
    await dialog_manager.switch_to(NewRequest.sent)


async def on_description_attachment(
    update: MessageCreated,
    widget: MessageInput,
    dialog_manager: DialogManager,
) -> None:
    await on_attachment(update, widget, dialog_manager)
    caption = (update.message.body.text or "").strip()
    if not caption:
        return
    with NewRequestData.proxy(dialog_manager) as data:
        data.description = caption
    await dialog_manager.switch_to(NewRequest.attachments)


async def on_start(_start_data: Any, dialog_manager: DialogManager) -> None:
    NewRequestData.load_start(dialog_manager).dump(dialog_manager)


async def get_cancel(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    return {
        "request_id": NewRequestData.load_start(dialog_manager).request_id,
        "reasons": [
            {"id": reason.value, "label": f"↩️ {CANCEL_REASONS[reason]}"}
            for reason in CancelReason
            if reason is not CancelReason.OTHER
        ],
    }


@inject
async def on_cancel_reason(
    callback: MessageCallback,
    _select: Any,
    dialog_manager: DialogManager,
    reason: str,
    requests_service: FromDishka[RequestsService],
) -> None:
    request_id = NewRequestData.load_start(dialog_manager).request_id
    if request_id is None:
        await dialog_manager.switch_to(NewRequest.sent)
        return
    try:
        await requests_service.cancel(
            dialog_user_id(dialog_manager),
            RequestId(request_id),
            CancelReason(reason),
            None,
        )
    except ZhekaError as error:
        await refused(callback, error)
        return
    await back_to_menu(
        dialog_manager,
        f"↩️ Заявка №{request_id} отменена",
        OPEN_REQUEST,
        request_app_path(RequestId(request_id)),
    )


@inject
async def get_description(
    dialog_manager: DialogManager,
    announcements_service: FromDishka[AnnouncementsService],
    **_: Any,
) -> dict[str, Any]:
    data = NewRequestData.load(dialog_manager)
    works = (
        None
        if data.house_id is None or data.category is None
        else await announcements_service.active_works(
            dialog_user_id(dialog_manager),
            HouseId(data.house_id),
            data.category,
        )
    )
    return {
        **await get_draft(dialog_manager),
        "works_until": None if works is None else f"{works.ends_at:{MOMENT}}",
    }


async def on_place(
    _callback: MessageCallback,
    button: Button,
    dialog_manager: DialogManager,
) -> None:
    with NewRequestData.proxy(dialog_manager) as data:
        data.place = RequestPlace(str(button.widget_id))
        described = bool(data.description)
    await dialog_manager.switch_to(
        NewRequest.attachments if described else NewRequest.description,
    )


async def on_description_back(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
) -> None:
    category = NewRequestData.load(dialog_manager).category
    asked = category is not None and category not in CATEGORY_PLACES
    await dialog_manager.switch_to(NewRequest.place if asked else NewRequest.category)


async def _after_category(dialog_manager: DialogManager) -> None:
    data = NewRequestData.load(dialog_manager)
    if data.place is None:
        await dialog_manager.switch_to(NewRequest.place)
        return
    await dialog_manager.switch_to(
        NewRequest.attachments if data.description else NewRequest.description,
    )


def _publish(
    dialog_manager: DialogManager,
    publisher: TaskPublisher,
    group_id: int | None,
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
        video_tokens=data.videos,
        channel=RequestChannel.BOT.value,
        stack_id=dialog_manager.current_stack().id,
        place=data.place,
        group_id=group_id,
    )


async def get_neighbours(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    return {"neighbours": NewRequestData.load(dialog_manager).neighbours}


@inject
async def on_me_too(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    publisher: FromDishka[TaskPublisher],
) -> None:
    with NewRequestData.proxy(dialog_manager) as data:
        if not data.description and data.category is not None:
            data.description = NEIGHBOUR_DESCRIPTION.format(
                CATEGORY_RULES[data.category].label.lower(),
            )
        data.place = data.place or RequestPlace.HOUSE
        group_id = data.group_id
    _publish(dialog_manager, publisher, group_id)
    await dialog_manager.switch_to(NewRequest.sent)


async def on_other(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
) -> None:
    with NewRequestData.proxy(dialog_manager) as data:
        data.group_id = None
    await _after_category(dialog_manager)
