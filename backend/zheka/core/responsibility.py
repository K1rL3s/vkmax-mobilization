from collections.abc import Mapping
from enum import StrEnum

from zheka.base import ZhekaType
from zheka.core.enums import (
    CATEGORY_PLACES,
    CityServiceKind,
    RequestCategory,
    RequestPlace,
)


class Spot(StrEnum):
    FLAT = "flat"
    ENTRANCE = "entrance"
    YARD = "yard"
    STREET = "street"


class Verdict(StrEnum):
    MANAGEMENT = "management"
    OWNER = "owner"
    UTILITY = "utility"
    EMERGENCY = "emergency"


SPOTS: Mapping[Spot, str] = {
    Spot.FLAT: "🏠 В квартире",
    Spot.ENTRANCE: "🚪 В подъезде или на крыше",
    Spot.YARD: "🌳 Во дворе",
    Spot.STREET: "🛣 На улице",
}


class Leaf(ZhekaType):
    spot: Spot
    label: str
    verdict: Verdict
    basis: str
    category: RequestCategory | None = None
    service: CityServiceKind | None = None

    @property
    def place(self) -> RequestPlace:
        fixed = None if self.category is None else CATEGORY_PLACES.get(self.category)
        if fixed is not None:
            return fixed
        return RequestPlace.FLAT if self.spot is Spot.FLAT else RequestPlace.HOUSE


OUTSIDE_THE_WALL = (
    "Сети за внешней стеной дома не входят в общее имущество (ПП 491, п. 8): "
    "их чинит ресурсная организация, а не УК"
)

LEAVES: Mapping[str, Leaf] = {
    "riser_leak": Leaf(
        spot=Spot.FLAT,
        label="💧 Течет стояк, батарея или труба до первого крана",
        verdict=Verdict.MANAGEMENT,
        basis=(
            "Стояки, отводы от них до первого крана с самим краном (ПП 491, п. 5) "
            "и батареи отопления (п. 6) входят в общее имущество дома. Батарею с "
            "кранами на подводке, которая греет только вашу квартиру, Минстрой "
            "относит к собственнику"
        ),
        category=RequestCategory.LEAK,
    ),
    "tap_leak": Leaf(
        spot=Spot.FLAT,
        label="🚿 Течет после первого крана: смеситель, подводка, разводка",
        verdict=Verdict.OWNER,
        basis=(
            "Общее имущество кончается первым краном на отводе от стояка "
            "(ПП 491, п. 5). Трубы, подводка и смесители после него - имущество "
            "собственника квартиры"
        ),
    ),
    "ceiling_leak": Leaf(
        spot=Spot.FLAT,
        label="🌧 Течет с потолка",
        verdict=Verdict.MANAGEMENT,
        category=RequestCategory.LEAK,
        basis=(
            "Аварийная служба УК найдет источник и перекроет воду. Течь из стояка "
            "чинит УК (ПП 491, п. 5), течь после крана в квартире сверху - ее "
            "собственник"
        ),
    ),
    "sink_clog": Leaf(
        spot=Spot.FLAT,
        label="🚽 Засор только у меня: раковина, ванна, унитаз",
        verdict=Verdict.OWNER,
        basis=(
            "Канализация дома - это стояки и ответвления от них до первых стыковых "
            "соединений (ПП 491, п. 5). Сифоны, унитаз и трубы квартиры до этого "
            "стыка чистит собственник. Если вода поднимается и у соседей, засор в "
            "общем стояке: это заявка в УК"
        ),
    ),
    "cold_radiator": Leaf(
        spot=Spot.FLAT,
        label="🥶 Холодные батареи",
        verdict=Verdict.MANAGEMENT,
        basis=(
            "Тепло приходит в квартиру по стоякам системы отопления дома, это "
            "общее имущество (ПП 491, п. 6), а перебои разбирает УК"
        ),
        category=RequestCategory.HEATING,
    ),
    "no_water": Leaf(
        spot=Spot.FLAT,
        label="🚰 Нет воды или идет холодная вместо горячей",
        verdict=Verdict.MANAGEMENT,
        basis=(
            "Вода приходит в квартиру по стоякам дома, это общее имущество "
            "(ПП 491, п. 5), а перебои разбирает УК. Если без воды весь квартал, "
            "авария на сети водоканала"
        ),
        category=RequestCategory.WATER_SUPPLY,
    ),
    "socket": Leaf(
        spot=Spot.FLAT,
        label="🔌 Розетка, выключатель или проводка в квартире",
        verdict=Verdict.OWNER,
        basis=(
            "Сеть дома доходит до квартирного счетчика электроэнергии "
            "(ПП 491, п. 7). Проводка, розетки и выключатели после него - "
            "имущество собственника"
        ),
    ),
    "gas_flat": Leaf(
        spot=Spot.FLAT,
        label="🔥 Пахнет газом",
        verdict=Verdict.EMERGENCY,
        basis=(
            "Не включайте и не выключайте свет, откройте окна, выйдите из квартиры "
            "и звоните 104 или 112 из безопасного места. Утечку устраняет "
            "аварийная газовая служба"
        ),
        service=CityServiceKind.GAS,
    ),
    "elevator": Leaf(
        spot=Spot.ENTRANCE,
        label="🛗 Лифт",
        verdict=Verdict.MANAGEMENT,
        basis="Лифты и лифтовые шахты - общее имущество дома (ПП 491, п. 2 «а»)",
        category=RequestCategory.ELEVATOR,
    ),
    "floor_panel": Leaf(
        spot=Spot.ENTRANCE,
        label="⚡️ Щиток на этаже или свет в подъезде",
        verdict=Verdict.MANAGEMENT,
        basis=(
            "Этажные щитки, освещение подъезда и сети до квартирных счетчиков - "
            "общее имущество (ПП 491, п. 7)"
        ),
        category=RequestCategory.ELECTRICITY,
    ),
    "chute": Leaf(
        spot=Spot.ENTRANCE,
        label="🗑 Мусоропровод",
        verdict=Verdict.MANAGEMENT,
        basis=(
            "Мусоропроводы и мусороприемные камеры - общее имущество (ПП 491, п. 2 «а»)"
        ),
        category=RequestCategory.GARBAGE,
    ),
    "entrance": Leaf(
        spot=Spot.ENTRANCE,
        label="🚪 Дверь, окно, перила или грязно в подъезде",
        verdict=Verdict.MANAGEMENT,
        basis=(
            "Лестницы и площадки, окна и двери подъезда, перила - общее имущество "
            "(ПП 491, п. 2 «а», «г»)"
        ),
        category=RequestCategory.ENTRANCE,
    ),
    "roof": Leaf(
        spot=Spot.ENTRANCE,
        label="🏚 Течет крыша",
        verdict=Verdict.MANAGEMENT,
        basis="Крыша - общее имущество дома (ПП 491, п. 2 «б»)",
        category=RequestCategory.LEAK,
    ),
    "bins_dirty": Leaf(
        spot=Spot.YARD,
        label="🧹 Грязно у мусорных контейнеров",
        verdict=Verdict.MANAGEMENT,
        basis=(
            "Участок дома с благоустройством - общее имущество (ПП 491, п. 2 «е»), "
            "уборка контейнерной площадки - работа УК (ПП 290, п. 26(1))"
        ),
        category=RequestCategory.GARBAGE,
    ),
    "bins_full": Leaf(
        spot=Spot.YARD,
        label="🚛 Не вывезли мусор из контейнеров",
        verdict=Verdict.UTILITY,
        basis=(
            "Вывоз отходов - коммунальная услуга регионального оператора. "
            "УК отвечает за саму площадку (ПП 491, п. 2 «е»)"
        ),
        service=CityServiceKind.WASTE,
    ),
    "yard": Leaf(
        spot=Spot.YARD,
        label="🌳 Двор, детская площадка, снег и наледь",
        verdict=Verdict.MANAGEMENT,
        basis=(
            "Участок дома с озеленением и благоустройством и детские площадки на "
            "нем - общее имущество (ПП 491, п. 2 «е», «ж»). Если участок не "
            "поставлен на кадастровый учет, за двор отвечает муниципалитет"
        ),
        category=RequestCategory.YARD,
    ),
    "water_main": Leaf(
        spot=Spot.STREET,
        label="⛲️ Бьет вода из-под земли",
        verdict=Verdict.UTILITY,
        basis=OUTSIDE_THE_WALL,
        service=CityServiceKind.WATER,
    ),
    "heat_main": Leaf(
        spot=Spot.STREET,
        label="♨️ Парит теплотрасса, без отопления весь квартал",
        verdict=Verdict.UTILITY,
        basis=OUTSIDE_THE_WALL,
        service=CityServiceKind.HEAT,
    ),
    "blackout": Leaf(
        spot=Spot.STREET,
        label="🌑 Нет света в нескольких домах",
        verdict=Verdict.UTILITY,
        basis=OUTSIDE_THE_WALL,
        service=CityServiceKind.ENERGY,
    ),
    "danger": Leaf(
        spot=Spot.STREET,
        label="🚨 Пожар, оборван провод, упало дерево",
        verdict=Verdict.EMERGENCY,
        basis="Угроза жизни и имуществу - сразу 112, не УК и не заявка",
    ),
}
