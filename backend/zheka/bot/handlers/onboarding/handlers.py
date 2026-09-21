from collections.abc import Sequence
from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager, StartMode
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput, MessageInput
from maxo.dialogs.widgets.kbd import Button, Select
from maxo.types import LocationAttachment, MessageCallback, MessageCreated

from zheka.bot.dialog_data import HouseItem, MenuData, OnboardingData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import Menu, Onboarding
from zheka.core.enums import ResidentRole
from zheka.core.services.houses import HouseFound, HousesService

# больше одной прокрутки житель все равно не пролистает, уточнить адрес дешевле
HOUSES_LIMIT = 30


def _house_items(found: Sequence[HouseFound]) -> list[HouseItem]:
    return [
        HouseItem(id=int(item.house.id), title=item.house.address) for item in found
    ]


@inject
async def get_cities(
    houses_service: FromDishka[HousesService], **_: Any
) -> dict[str, Any]:
    cities = await houses_service.cities(None, None)
    return {"cities": [city for _region, city in cities]}


@inject
async def get_streets(
    dialog_manager: DialogManager, houses_service: FromDishka[HousesService], **_: Any
) -> dict[str, Any]:
    city = OnboardingData.load(dialog_manager).city
    return {"city": city, "streets": await houses_service.streets(city, None, None)}


async def get_houses(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    # ни одного запроса: дома в данные диалога кладет тот шаг, который их нашел,
    # и выбор улицы, и геолокация, - поэтому окно у них общее
    return {"houses": OnboardingData.load(dialog_manager).houses}


@inject
async def get_flat(
    dialog_manager: DialogManager, houses_service: FromDishka[HousesService], **_: Any
) -> dict[str, Any]:
    house_id = OnboardingData.load(dialog_manager).chosen_house()
    card = await houses_service.house_card(house_id, dialog_user_id(dialog_manager))
    return {"address": card.house.address}


async def on_city(
    _callback: MessageCallback,
    _select: Select[str],
    dialog_manager: DialogManager,
    city: str,
) -> None:
    with OnboardingData.proxy(dialog_manager) as data:
        data.city = city
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
    with OnboardingData.proxy(dialog_manager) as data:
        found, _total = await houses_service.search(
            dialog_user_id(dialog_manager),
            data.city,
            street,
            None,
            None,
            HOUSES_LIMIT,
            0,
        )
        data.houses = _house_items(found)
    await dialog_manager.switch_to(Onboarding.house)


async def on_house(
    _callback: MessageCallback,
    _select: Select[int],
    dialog_manager: DialogManager,
    house_id: int,
) -> None:
    with OnboardingData.proxy(dialog_manager) as data:
        data.house_id = house_id
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
        dialog_user_id(dialog_manager),
        location.latitude,
        location.longitude,
        radius_m=700,
        limit=HOUSES_LIMIT,
    )
    with OnboardingData.proxy(dialog_manager) as data:
        data.houses = _house_items(found)
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
    # источник и подъезд кладет сюда тот, кто привел жителя в дом
    data = OnboardingData.load(dialog_manager)
    await houses_service.link(
        dialog_user_id(dialog_manager),
        data.chosen_house(),
        None,
        flat_number,
        ResidentRole.OWNER,
        data.source,
        data.entrance,
    )
    await dialog_manager.start(
        Menu.main,
        data=MenuData(notice="Дом добавлен").to_data(),
        mode=StartMode.RESET_STACK,
    )


async def on_start(_start_data: Any, dialog_manager: DialogManager) -> None:
    # диплинк кладет дом в start_data, выбор руками - в dialog_data
    OnboardingData.load_start(dialog_manager).dump(dialog_manager)
