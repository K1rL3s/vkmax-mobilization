from collections.abc import Sequence
from html import escape
from typing import Any

from dishka import FromDishka
from maxo.dialogs import DialogManager
from maxo.dialogs.integrations.dishka import inject
from maxo.dialogs.widgets.input import ManagedTextInput, MessageInput
from maxo.dialogs.widgets.kbd import Button, Select
from maxo.types import LocationAttachment, MessageCallback, MessageCreated

from zheka.bot.cards import back_to_menu
from zheka.bot.dialog_data import HouseItem, OnboardingData
from zheka.bot.middlewares.user import dialog_user_id
from zheka.bot.states import Onboarding
from zheka.core.enums import EventSource, ResidentRole
from zheka.core.ids import FlatId
from zheka.core.services.houses import HouseFound, HousesService

HOUSES_LIMIT = 30
FLATS_LIMIT = 300
HOUSE_LINKED = "✅ Дом добавлен: {address}"


def _house_items(found: Sequence[HouseFound], *, by_geo: bool) -> list[HouseItem]:
    return [
        HouseItem(
            id=int(item.house.id),
            title=item.house.street_address if by_geo else item.house.building,
        )
        for item in found
    ]


@inject
async def get_cities(
    dialog_manager: DialogManager,
    houses_service: FromDishka[HousesService],
    **_: Any,
) -> dict[str, Any]:
    data = OnboardingData.load(dialog_manager)
    cities = await houses_service.cities(None, data.query or None)
    return {
        "cities": [city for _region, city in cities],
        "missed": data.missed and escape(data.missed),
    }


@inject
async def get_streets(
    dialog_manager: DialogManager,
    houses_service: FromDishka[HousesService],
    **_: Any,
) -> dict[str, Any]:
    data = OnboardingData.load(dialog_manager)
    return {
        "city": escape(data.city),
        "streets": await houses_service.streets(data.city, None, data.query or None),
        "missed": data.missed and escape(data.missed),
    }


async def get_houses(dialog_manager: DialogManager, **_: Any) -> dict[str, Any]:
    data = OnboardingData.load(dialog_manager)
    return {
        "street": escape(data.street),
        "by_geo": data.by_geo,
        "houses": _matching(data.houses, data.query),
        "missed": data.missed and escape(data.missed),
    }


@inject
async def get_flat(
    dialog_manager: DialogManager,
    houses_service: FromDishka[HousesService],
    **_: Any,
) -> dict[str, Any]:
    data = OnboardingData.load(dialog_manager)
    house_id = data.chosen_house()
    card = await houses_service.house_card(house_id, dialog_user_id(dialog_manager))
    flats = await houses_service.house_flats(house_id, FLATS_LIMIT)
    return {
        "address": escape(card.house.address),
        "flats": flats,
        "has_houses": bool(data.houses),
    }


async def on_city(
    _callback: MessageCallback,
    _select: Select[str],
    dialog_manager: DialogManager,
    city: str,
) -> None:
    await _pick_city(dialog_manager, city)


@inject
async def on_street(
    _callback: MessageCallback,
    _select: Any,
    dialog_manager: DialogManager,
    street: str,
    houses_service: FromDishka[HousesService],
) -> None:
    await _pick_street(dialog_manager, houses_service, street)


async def on_house(
    _callback: MessageCallback,
    _select: Select[int],
    dialog_manager: DialogManager,
    house_id: int,
) -> None:
    await _pick_house(dialog_manager, house_id)


@inject
async def on_location(
    update: MessageCreated,
    _widget: MessageInput,
    dialog_manager: DialogManager,
    houses_service: FromDishka[HousesService],
) -> None:
    location = next(
        attach
        for attach in update.message.body.attachments or []
        if isinstance(attach, LocationAttachment)
    )
    found = await houses_service.nearest(
        dialog_user_id(dialog_manager),
        location.latitude,
        location.longitude,
        radius_m=700,
        limit=HOUSES_LIMIT,
    )
    with OnboardingData.proxy(dialog_manager) as data:
        data.houses = _house_items(found, by_geo=True)
        data.by_geo, data.query, data.missed = True, "", None
    _first_page(dialog_manager, "houses_scroll")
    await dialog_manager.switch_to(Onboarding.house)


@inject
async def on_flat_number(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    number: str,
    houses_service: FromDishka[HousesService],
) -> None:
    await link_house(dialog_manager, houses_service, None, number)


@inject
async def on_flat_skip(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
    houses_service: FromDishka[HousesService],
) -> None:
    await link_house(dialog_manager, houses_service, None, None)


async def link_house(
    dialog_manager: DialogManager,
    houses_service: HousesService,
    flat_id: FlatId | None,
    flat_number: str | None,
) -> None:
    data = OnboardingData.load(dialog_manager)
    view = await houses_service.link(
        dialog_user_id(dialog_manager),
        data.chosen_house(),
        flat_id,
        flat_number,
        ResidentRole.OWNER,
        data.source,
        data.entrance,
    )
    await back_to_menu(
        dialog_manager,
        HOUSE_LINKED.format(address=escape(view.house.address)),
    )


async def on_start(_start_data: Any, dialog_manager: DialogManager) -> None:
    OnboardingData.load_start(dialog_manager).dump(dialog_manager)


@inject
async def on_city_text(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    text: str,
    houses_service: FromDishka[HousesService],
) -> None:
    text = text.strip()
    _first_page(dialog_manager, "cities_scroll")
    cities = [city for _region, city in await houses_service.cities(None, text)]
    if len(cities) == 1:
        await _pick_city(dialog_manager, cities[0])
        return
    with OnboardingData.proxy(dialog_manager) as data:
        data.query, data.missed = (text, None) if cities else ("", text)


@inject
async def on_street_text(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    text: str,
    houses_service: FromDishka[HousesService],
) -> None:
    text = text.strip()
    _first_page(dialog_manager, "streets_scroll")
    city = OnboardingData.load(dialog_manager).city
    streets = await houses_service.streets(city, None, text)
    if len(streets) == 1:
        await _pick_street(dialog_manager, houses_service, streets[0])
        return
    with OnboardingData.proxy(dialog_manager) as data:
        data.query, data.missed = (text, None) if streets else ("", text)


@inject
async def on_house_text(
    _update: MessageCreated,
    _widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    text: str,
    houses_service: FromDishka[HousesService],
) -> None:
    text = text.strip()
    _first_page(dialog_manager, "houses_scroll")
    data = OnboardingData.load(dialog_manager)
    if data.by_geo:
        houses = _matching(data.houses, text)
    else:
        found, _total = await houses_service.search(
            dialog_user_id(dialog_manager),
            data.city,
            data.street,
            text,
            None,
            HOUSES_LIMIT,
            0,
        )
        houses = _house_items(found, by_geo=False)
    if len(houses) == 1:
        await _pick_house(dialog_manager, houses[0].id)
        return
    with OnboardingData.proxy(dialog_manager) as data:
        if data.by_geo:
            data.query = text if houses else ""
        else:
            data.houses = houses or data.houses
        data.missed = None if houses else text


async def on_back(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
) -> None:
    with OnboardingData.proxy(dialog_manager) as data:
        data.query, data.missed = "", None


async def _pick_city(dialog_manager: DialogManager, city: str) -> None:
    with OnboardingData.proxy(dialog_manager) as data:
        data.city, data.query, data.missed = city, "", None
    _first_page(dialog_manager, "streets_scroll")
    await dialog_manager.switch_to(Onboarding.street)


async def _pick_street(
    dialog_manager: DialogManager,
    houses_service: HousesService,
    street: str,
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
        data.street, data.query, data.missed, data.by_geo = street, "", None, False
        data.houses = _house_items(found, by_geo=False)
    _first_page(dialog_manager, "houses_scroll")
    await dialog_manager.switch_to(Onboarding.house)


async def _pick_house(dialog_manager: DialogManager, house_id: int) -> None:
    with OnboardingData.proxy(dialog_manager) as data:
        data.house_id, data.missed = house_id, None
    _first_page(dialog_manager, "flats_scroll")
    await dialog_manager.switch_to(Onboarding.flat)


@inject
async def on_flat(
    _callback: MessageCallback,
    _select: Any,
    dialog_manager: DialogManager,
    flat_id: int,
    houses_service: FromDishka[HousesService],
) -> None:
    await link_house(dialog_manager, houses_service, FlatId(flat_id), None)


def _matching(houses: list[HouseItem], text: str) -> list[HouseItem]:
    needle = text.casefold()
    return [house for house in houses if needle in house.title.casefold()]


def _first_page(dialog_manager: DialogManager, scroll_id: str) -> None:
    dialog_manager.current_context().widget_data.pop(scroll_id, None)


async def on_leave_house(
    _callback: MessageCallback,
    _button: Button,
    dialog_manager: DialogManager,
) -> None:
    with OnboardingData.proxy(dialog_manager) as data:
        data.query, data.missed = "", None
        data.entrance, data.source = None, EventSource.DIRECT
