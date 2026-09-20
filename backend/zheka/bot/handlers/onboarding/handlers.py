from collections.abc import Sequence
from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager, StartMode
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput, MessageInput
from maxo.dialogs.widgets.kbd import Button, Select
from maxo.types import LocationAttachment, MessageCallback, MessageCreated

from zheka.bot.middlewares.user import USER_KEY
from zheka.bot.states import Menu, Onboarding
from zheka.core.enums import EventSource, ResidentRole
from zheka.core.ids import HouseId, UserId
from zheka.core.models import User
from zheka.core.services.houses import HouseFound, HousesService

# больше одной прокрутки житель все равно не пролистает, уточнить адрес дешевле
HOUSES_LIMIT = 30
NEARBY_RADIUS_M = 700

LINKED = "Дом добавлен"


def _house_items(found: Sequence[HouseFound]) -> list[dict[str, Any]]:
    return [{"id": int(item.house.id), "title": item.house.address} for item in found]


def _user_id(dialog_manager: DialogManager) -> UserId:
    user: User = dialog_manager.middleware_data[USER_KEY]
    return UserId(user.id)


def _context(dialog_manager: DialogManager) -> dict[str, Any]:
    # диплинк приводит жителя сразу на шаг квартиры и кладет дом, подъезд и
    # источник в start_data, а выбор адреса руками - в данные диалога
    start_data = dialog_manager.start_data
    data = dict(start_data) if isinstance(start_data, dict) else {}
    data.update(dialog_manager.dialog_data)
    return data


@inject
async def get_cities(
    houses_service: FromDishka[HousesService],
    **_: Any,
) -> dict[str, Any]:
    cities = await houses_service.cities(None, None)
    return {"cities": [city for _region, city in cities]}


@inject
async def get_streets(
    dialog_manager: DialogManager,
    houses_service: FromDishka[HousesService],
    **_: Any,
) -> dict[str, Any]:
    city = dialog_manager.dialog_data["city"]
    return {"city": city, "streets": await houses_service.streets(city, None, None)}


async def get_houses(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    # ни одного запроса: дома в данные диалога кладет тот шаг, который их нашел,
    # и выбор улицы, и геолокация, - поэтому окно у них общее
    return {"houses": dialog_manager.dialog_data.get("houses", [])}


@inject
async def get_flat(
    dialog_manager: DialogManager,
    houses_service: FromDishka[HousesService],
    **_: Any,
) -> dict[str, Any]:
    house_id = HouseId(_context(dialog_manager)["house_id"])
    card = await houses_service.house_card(house_id, _user_id(dialog_manager))
    return {"address": card.house.address}


async def on_city(
    _callback: MessageCallback,
    _select: Select[str],
    dialog_manager: DialogManager,
    city: str,
) -> None:
    dialog_manager.dialog_data["city"] = city
    await dialog_manager.switch_to(Onboarding.street)


@inject
async def on_street(
    _callback: MessageCallback,
    # Any, а не Select[str]: overload у inject разбирает четырехаргументный
    # колбэк только с ManagedWidget, а Select им не является
    _select: Any,
    dialog_manager: DialogManager,
    street: str,
    houses_service: FromDishka[HousesService],
) -> None:
    found, _total = await houses_service.search(
        _user_id(dialog_manager),
        dialog_manager.dialog_data["city"],
        street,
        None,
        None,
        HOUSES_LIMIT,
        0,
    )
    dialog_manager.dialog_data["houses"] = _house_items(found)
    await dialog_manager.switch_to(Onboarding.house)


async def on_house(
    _callback: MessageCallback,
    _select: Select[int],
    dialog_manager: DialogManager,
    house_id: int,
) -> None:
    dialog_manager.dialog_data["house_id"] = house_id
    await dialog_manager.switch_to(Onboarding.flat)


@inject
async def on_location(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    houses_service: FromDishka[HousesService],
) -> None:
    location = next(
        (
            attach
            for attach in update.message.body.attachments or []
            if isinstance(attach, LocationAttachment)
        ),
        None,
    )
    if location is None:
        return

    found = await houses_service.nearest(
        _user_id(dialog_manager),
        location.latitude,
        location.longitude,
        NEARBY_RADIUS_M,
        HOUSES_LIMIT,
    )
    dialog_manager.dialog_data["houses"] = _house_items(found)
    await dialog_manager.switch_to(Onboarding.house)


@inject
async def on_flat_number(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    number: str,
    houses_service: FromDishka[HousesService],
) -> None:
    await link_house(dialog_manager, houses_service, number)


@inject
async def on_flat_skip(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    houses_service: FromDishka[HousesService],
) -> None:
    await link_house(dialog_manager, houses_service, None)


async def link_house(
    dialog_manager: DialogManager,
    houses_service: HousesService,
    flat_number: str | None,
) -> None:
    # источник и подъезд кладет сюда тот, кто привел жителя в дом. HOUSE_LINKED
    # пишет сам сервис, и второй записи тут быть не должно
    data = _context(dialog_manager)
    await houses_service.link(
        _user_id(dialog_manager),
        HouseId(data["house_id"]),
        None,
        flat_number,
        ResidentRole.OWNER,
        EventSource(data.get("source", EventSource.DIRECT)),
        data.get("entrance"),
    )
    await dialog_manager.start(
        Menu.main,
        data={"notice": LINKED},
        mode=StartMode.RESET_STACK,
    )
