from magic_filter import F
from maxo.dialogs import Dialog, Window
from maxo.dialogs.widgets.input import MessageInput, TextInput
from maxo.dialogs.widgets.kbd import (
    Button,
    Cancel,
    RequestLocation,
    ScrollingGroup,
    Select,
    SwitchTo,
)
from maxo.dialogs.widgets.text import Const, Format
from maxo.enums import AttachmentType

from zheka.bot.handlers.onboarding.handlers import (
    get_cities,
    get_flat,
    get_houses,
    get_streets,
    on_city,
    on_flat_number,
    on_flat_skip,
    on_house,
    on_location,
    on_street,
)
from zheka.bot.states import Onboarding

PAGE = 8

METHOD_TEXT = "Как будем искать дом?"
CITY_TEXT = "Выбери город"
STREET_TEXT = "Выбери улицу"
HOUSE_TEXT = "Выбери дом"
NO_HOUSES_TEXT = "Рядом ничего не нашлось. Попробуй выбрать адрес вручную."
GEO_TEXT = "Пришли геопозицию, и я поищу дома рядом"
FLAT_TEXT = "{address}\n\nНапиши номер квартиры или пропусти этот шаг."

onboarding_dialog = Dialog(
    Window(
        Const(METHOD_TEXT),
        SwitchTo(Const("Выбрать адрес"), id="by_address", state=Onboarding.city),
        SwitchTo(Const("По геолокации"), id="by_geo", state=Onboarding.geo),
        Cancel(Const("Отмена")),
        state=Onboarding.method,
    ),
    Window(
        Const(CITY_TEXT),
        ScrollingGroup(
            Select(
                Format("{item}"),
                id="city",
                item_id_getter=lambda city: city,
                items="cities",
                on_click=on_city,
            ),
            id="cities_scroll",
            width=1,
            height=PAGE,
        ),
        state=Onboarding.city,
        getter=get_cities,
    ),
    Window(
        Const(STREET_TEXT),
        ScrollingGroup(
            Select(
                Format("{item}"),
                id="street",
                item_id_getter=lambda street: street,
                items="streets",
                on_click=on_street,
            ),
            id="streets_scroll",
            width=1,
            height=PAGE,
        ),
        SwitchTo(Const("Назад к городам"), id="to_cities", state=Onboarding.city),
        state=Onboarding.street,
        getter=get_streets,
    ),
    Window(
        Const(HOUSE_TEXT, when=F["houses"]),
        Const(NO_HOUSES_TEXT, when=~F["houses"]),
        ScrollingGroup(
            Select(
                Format("{item[title]}"),
                id="house",
                item_id_getter=lambda house: house["id"],
                type_factory=int,
                items="houses",
                on_click=on_house,
            ),
            id="houses_scroll",
            width=1,
            height=PAGE,
        ),
        SwitchTo(Const("Искать заново"), id="to_method", state=Onboarding.method),
        state=Onboarding.house,
        getter=get_houses,
    ),
    Window(
        Const(GEO_TEXT),
        RequestLocation(Const("Отправить геопозицию")),
        MessageInput(on_location, content_types=[AttachmentType.LOCATION]),
        SwitchTo(Const("Выбрать адрес"), id="geo_to_address", state=Onboarding.city),
        state=Onboarding.geo,
    ),
    Window(
        Format(FLAT_TEXT),
        TextInput(id="flat_number", on_success=on_flat_number),
        Button(Const("Пропустить"), id="skip_flat", on_click=on_flat_skip),
        state=Onboarding.flat,
        getter=get_flat,
    ),
)
