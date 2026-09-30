from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import MessageInput, TextInput
from maxo.dialogs.widgets.kbd import (
    Button,
    RequestLocation,
    Row,
    ScrollingGroup,
    Select,
    SwitchTo,
)
from maxo.dialogs.widgets.text import Const, Format, Multi
from maxo.enums import AttachmentType

from zheka.bot.cards import BACK, TO_MENU
from zheka.bot.handlers.onboarding.handlers import (
    get_cities,
    get_flat,
    get_houses,
    get_streets,
    on_back,
    on_city,
    on_city_text,
    on_flat,
    on_flat_number,
    on_flat_skip,
    on_house,
    on_house_text,
    on_leave_house,
    on_location,
    on_start,
    on_street,
    on_street_text,
)
from zheka.bot.states import Onboarding

PAGE = 8

METHOD_TEXT = "🔎 Как будем искать дом?"
CITY_TEXT = "🌆 Выберите город из списка или напишите его название"
STREET_TEXT = "🚦 {city}: выберите улицу из списка или напишите ее название"
HOUSE_TEXT = "🏢 {street}: выберите дом из списка или напишите его номер"
NEARBY_TEXT = "📍 Дома рядом с вами: выберите свой из списка или напишите номер дома"
NOTHING_NEAR_TEXT = "😔 Рядом ничего не нашлось, попробуйте выбрать адрес"
MISSED_TEXT = "😔 Не нашлось «{missed}», попробуйте написать иначе"
FLAT_NUMBER_TEXT = "🏢 {address}\n\n🚪 Напишите номер квартиры или пропустите этот шаг"
FLAT_LIST_TEXT = "🏢 {address}\n\n🚪 Выберите квартиру из списка или напишите ее номер"

MISSED = Format(MISSED_TEXT, when=F["missed"])

onboarding_dialog = Dialog(
    Window(
        Const(METHOD_TEXT),
        SwitchTo(Const("🧭 Выбрать адрес"), id="by_address", state=Onboarding.city),
        RequestLocation(Const("📍 По геолокации")),
        MessageInput(on_location, content_types=[AttachmentType.LOCATION]),
        TO_MENU,
        state=Onboarding.method,
    ),
    Window(
        Multi(Const(CITY_TEXT), MISSED, sep="\n\n"),
        ScrollingGroup(
            Select(
                Format("🌆 {item}"),
                id="city",
                item_id_getter=lambda city: city,
                items="cities",
                on_click=on_city,
            ),
            id="cities_scroll",
            width=1,
            height=PAGE,
            hide_on_single_page=True,
        ),
        TextInput(id="city_text", on_success=on_city_text),
        Row(
            SwitchTo(BACK, id="city_back", state=Onboarding.method, on_click=on_back),
            TO_MENU,
        ),
        state=Onboarding.city,
        getter=get_cities,
    ),
    Window(
        Multi(Format(STREET_TEXT), MISSED, sep="\n\n"),
        ScrollingGroup(
            Select(
                Format("🚦 {item}"),
                id="street",
                item_id_getter=lambda street: street,
                items="streets",
                on_click=on_street,
            ),
            id="streets_scroll",
            width=1,
            height=PAGE,
            hide_on_single_page=True,
        ),
        TextInput(id="street_text", on_success=on_street_text),
        Row(
            SwitchTo(BACK, id="street_back", state=Onboarding.city, on_click=on_back),
            TO_MENU,
        ),
        state=Onboarding.street,
        getter=get_streets,
    ),
    Window(
        Multi(
            Format(HOUSE_TEXT, when=~F["by_geo"]),
            Const(NEARBY_TEXT, when=F["by_geo"] & F["houses"]),
            Const(NOTHING_NEAR_TEXT, when=F["by_geo"] & ~F["houses"]),
            MISSED,
            sep="\n\n",
        ),
        ScrollingGroup(
            Select(
                Format("🏢 {item.title}"),
                id="house",
                item_id_getter=lambda house: house.id,
                type_factory=int,
                items="houses",
                on_click=on_house,
            ),
            id="houses_scroll",
            width=1,
            height=PAGE,
            hide_on_single_page=True,
        ),
        TextInput(id="house_text", on_success=on_house_text),
        Row(
            SwitchTo(
                BACK,
                id="house_to_street",
                state=Onboarding.street,
                on_click=on_back,
                when=~F["by_geo"],
            ),
            SwitchTo(
                BACK,
                id="house_to_method",
                state=Onboarding.method,
                on_click=on_back,
                when=F["by_geo"],
            ),
            TO_MENU,
        ),
        state=Onboarding.house,
        getter=get_houses,
    ),
    Window(
        Format(FLAT_LIST_TEXT, when=F["flats"]),
        Format(FLAT_NUMBER_TEXT, when=~F["flats"]),
        ScrollingGroup(
            Select(
                Format("{item.number}"),
                id="flat",
                item_id_getter=lambda flat: flat.id,
                type_factory=int,
                items="flats",
                on_click=on_flat,
            ),
            id="flats_scroll",
            width=4,
            height=6,
            hide_on_single_page=True,
        ),
        TextInput(id="flat_number", on_success=on_flat_number),
        Button(Const("⏩ Пропустить"), id="skip_flat", on_click=on_flat_skip),
        Row(
            SwitchTo(
                BACK,
                id="flat_to_houses",
                state=Onboarding.house,
                on_click=on_back,
                when=F["has_houses"],
            ),
            SwitchTo(
                BACK,
                id="flat_to_method",
                state=Onboarding.method,
                on_click=on_leave_house,
                when=~F["has_houses"],
            ),
            TO_MENU,
        ),
        state=Onboarding.flat,
        getter=get_flat,
    ),
    on_start=on_start,
)
