"""Скачивает открытые данные для сида и пишет компактные CSV в zheka/seed/data

Запускается руками один раз, результат коммитится: сам сид в сеть не ходит.
Источники: АИС ППК «ФРТ» (Реформа ЖКХ) - набор КР 1.1 по трем регионам,
реестр управляющих организаций и карточки домов; координаты - Nominatim,
а чего он не нашел - Overpass API, (c) OpenStreetMap contributors, ODbL 1.0.
Полные выгрузки лежат в кеше backend/.cache/seed, он в .gitignore.

    uv run python scripts/fetch_seed_data.py
"""

import csv
import html
import io
import json
import logging
import re
import time
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from decimal import Decimal
from math import ceil
from pathlib import Path
from typing import NamedTuple

BACKEND_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = BACKEND_ROOT / ".cache" / "seed"
DATA_DIR = BACKEND_ROOT / "zheka" / "seed" / "data"

REFORMA = "https://www.reformagkh.ru"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = "zheka-seed-fetch/1.0 (MAX hackathon demo seed, one-off run)"
# Nominatim просит не чаще одного запроса в секунду, карточкам Реформы
# хватает той же вежливости
REQUEST_INTERVAL = 1.1
REGISTRY_EXPORT = 1
# около километра вокруг найденных домов улицы, в градусах
BBOX_PAD = 0.01
HOUSES_PER_STREET = 55
# типографские тире из источников (U+2010-U+2015, U+2212): в репозитории
# только ASCII-дефис
DASHES = re.compile("[" + chr(0x2010) + "-" + chr(0x2015) + chr(0x2212) + "]")

log = logging.getLogger("fetch_seed_data")


class Street(NamedTuple):
    export_id: int
    subject_rf: str
    region: str
    city: str
    street: str
    prefix: str
    mun_obr: str
    timezone: str


STREETS = (
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Ленинский проспект",
        prefix="Ленинский просп. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="Гражданский проспект",
        prefix="Гражданский пр., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="проспект Победы",
        prefix="пр-кт. Победы, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
)

HOUSE_FIELDS = (
    "region",
    "city",
    "street",
    "building",
    "built_year",
    "floors",
    "area",
    "entrances",
    "living_flats",
    "living_area",
    "overhaul_rate",
    "lat",
    "lon",
    "org_inn",
    "source_id",
    "timezone",
)
ORG_FIELDS = ("inn", "name", "phone", "address", "timezone")
# городской номер из семи цифр без кода не дозвонится с мобильного, а код у
# региона один. В Москве их два, но московские номера в реестре все с кодом
FULL_DIGITS = 11
LOCAL_DIGITS = 7
AREA_CODES = {"город Санкт-Петербург": "812", "Республика Татарстан": "843"}

_last_request = 0.0


def _get(url: str) -> bytes:
    global _last_request  # noqa: PLW0603
    wait = _last_request + REQUEST_INTERVAL - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    # без Accept openresty перед Реформой отвечает нестандартным 477
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    request = urllib.request.Request(url, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            return bytes(response.read())
    finally:
        _last_request = time.monotonic()


def _cached(name: str, url: str) -> bytes:
    path = CACHE_DIR / name
    if not path.exists():
        log.info("GET %s", url)
        path.write_bytes(_get(url))
    return path.read_bytes()


def _export_rows(export_id: int) -> Iterator[dict[str, str]]:
    raw = _cached(f"export-{export_id}.zip", f"{REFORMA}/opendata/export/{export_id}")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        (name,) = archive.namelist()
        text = archive.read(name).decode("utf-8-sig")
    yield from csv.DictReader(io.StringIO(text), delimiter=";")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", DASHES.sub("-", value)).strip()


def _scaled(value: str, scale: int) -> int:
    # "32,63" -> 326300 при scale=10000: целое без float, как в AGENTS.md
    return int(Decimal(value.replace(",", ".")) * scale)


def _building_key(building: str) -> tuple[int, str]:
    match = re.match(r"\d+", building)
    return (int(match.group()) if match else 0, building)


def _card(source_id: str) -> tuple[int | None, str | None]:
    page = _cached(
        f"card-{source_id}.html", f"{REFORMA}/myhouse/profile/view/{source_id}"
    ).decode("utf-8")
    entrances, manager = parse_card(page)
    if manager is None and "Домом управляет" in page:
        log.info("карточка %s называет УК, но имя не разобрано", source_id)
    return entrances, manager


def parse_card(page: str) -> tuple[int | None, str | None]:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
    entrances = re.search(r"Количество подъездов, ед\. (\d+)", text)
    # у карточки без договора управления за именем сразу идут услуги
    manager = re.search(
        r"Домом управляет (.+?) (?:Дата начала управления|Вид коммунальной услуги)",
        text,
    )
    return (
        int(entrances.group(1)) if entrances else None,
        _clean(html.unescape(manager.group(1))) if manager else None,
    )


def house_number(value: str) -> str:
    value = value.lower().replace("корпус", "к").replace("корп.", "к")
    value = value.replace("к.", "к").replace("с.", "с")
    value = re.sub(r"лит(ера)?\.?\s*\S+", "", value)
    return re.sub(r"[\s,]", "", value)


def _geocode(street: Street, building: str) -> tuple[str, str]:
    number = house_number(building)
    query = f"{street.city}, {street.street}, {number}"
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "ru",
            "addressdetails": 1,
        }
    )
    safe = re.sub(r"\W+", "_", query)
    found = json.loads(_cached(f"geo-{safe}.json", f"{NOMINATIM}?{params}"))
    # только точное попадание в дом: соседний номер или улица целиком дали бы
    # координаты другого здания
    if not found or (
        house_number(found[0].get("address", {}).get("house_number", "")) != number
    ):
        return "", ""
    return found[0]["lat"], found[0]["lon"]


def _pick(street: Street) -> list[dict[str, str]]:
    # части дома «(пар. 1-2)» дублируют адрес, а без house_id нет карточки
    picked = [
        row
        for row in _export_rows(street.export_id)
        if row["address"].startswith(street.prefix)
        and row["mun_obr"].startswith(street.mun_obr)
        and "(" not in row["address"]
        and row["house_id"]
        and row["living_rooms_amount"]
        and int(row["living_rooms_amount"]) > 0
        and row["number_floors_max"]
        and row["owners_payment"]
    ]
    picked.sort(key=lambda row: _building_key(row["address"][len(street.prefix) :]))
    return picked[:HOUSES_PER_STREET]


def _registry() -> dict[tuple[str, str], list[dict[str, str]]]:
    by_name: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in _export_rows(REGISTRY_EXPORT):
        for name in {row["name_short"], row["name_full"]}:
            by_name[row["subject_rf"], _clean(name).lower()].append(row)
    return by_name


def _org(row: dict[str, str], timezone: str) -> dict[str, str]:
    return {
        "inn": row["inn"],
        "name": _clean(row["name_short"]),
        "phone": phone(row["phone"], AREA_CODES.get(row["subject_rf"])),
        "address": _clean(row["actual_address"] or row["legal_address"]),
        "timezone": timezone,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    registry = _registry()

    houses = []
    orgs: dict[str, dict[str, str]] = {}
    for street in STREETS:
        street_houses: list[dict[str, str | int]] = []
        for row in _pick(street):
            building = _clean(row["address"][len(street.prefix) :])
            building = building.replace(", корп.", " корп.")
            entrances, manager = _card(row["house_id"])
            floors = int(row["number_floors_max"])
            living_flats = int(row["living_rooms_amount"])
            if not entrances:
                # карточка без подъездов: оценка по квартирам, по четыре на этаж
                entrances = max(1, ceil(living_flats / (floors * 4)))
                log.info("нет подъездов в карточке %s, оценка %s", building, entrances)
            org_inn = ""
            if manager is not None:
                matches = {
                    candidate["inn"]: candidate
                    for candidate in registry.get(
                        (street.subject_rf, manager.lower()), []
                    )
                }
                # одноименные УК в регионе - не повод выбирать наугад
                if len(matches) == 1:
                    ((org_inn, org),) = matches.items()
                    orgs[org_inn] = _org(org, street.timezone)
                else:
                    log.info(
                        "УК %r у %s: совпадений %s", manager, building, len(matches)
                    )
            lat, lon = _geocode(street, building)
            street_houses.append(
                {
                    "region": street.region,
                    "city": street.city,
                    "street": street.street,
                    "building": building,
                    "built_year": row["commission_year"],
                    "floors": floors,
                    "area": _scaled(row["total_sq"], 100),
                    "entrances": entrances,
                    "living_flats": living_flats,
                    "living_area": _scaled(row["living_rooms_sq"], 100),
                    "overhaul_rate": _scaled(row["owners_payment"], 10000),
                    "lat": lat,
                    "lon": lon,
                    "org_inn": org_inn,
                    "source_id": row["house_id"],
                    "timezone": street.timezone,
                }
            )
        _fill_from_osm(street, street_houses)
        houses.extend(street_houses)

    with (DATA_DIR / "houses.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, HOUSE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(houses)
    with (DATA_DIR / "organizations.csv").open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.DictWriter(file, ORG_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(orgs.values(), key=lambda org: org["inn"]))
    log.info(
        "домов %s, с координатами %s, с УК %s, организаций %s",
        len(houses),
        sum(1 for house in houses if house["lat"]),
        sum(1 for house in houses if house["org_inn"]),
        len(orgs),
    )


def phone(value: str, area_code: str | None) -> str:
    # кнопка «Позвонить» открывает tel: с этим значением, поэтому здесь
    # только номер, который можно набрать, или пусто
    first = re.split(r"[,;]", value)[0]
    digits = re.sub(r"\D", "", first)
    if len(digits) == FULL_DIGITS and digits[0] in "78":
        return f"+7{digits[1:]}"
    if len(digits) == FULL_DIGITS - 1:
        return f"+7{digits}"
    if len(digits) == LOCAL_DIGITS and area_code is not None:
        return f"+7{area_code}{digits}"
    return ""


def _fill_from_osm(street: Street, houses: list[dict[str, str | int]]) -> None:
    # Nominatim по свободному запросу ранжирует выше дома с тем же номером
    # корпуса на другом конце улицы и не находит часть домов, которые в OSM
    # есть. Overpass отдает все адреса улицы разом, их сверяем сами
    missing = [house for house in houses if not house["lat"]]
    found = [
        (float(house["lat"]), float(house["lon"])) for house in houses if house["lat"]
    ]
    if not missing or not found:
        return
    south = min(lat for lat, _ in found) - BBOX_PAD
    west = min(lon for _, lon in found) - BBOX_PAD
    north = max(lat for lat, _ in found) + BBOX_PAD
    east = max(lon for _, lon in found) + BBOX_PAD
    # запрос по границе города Overpass не успевает выполнить за таймаут
    query = (
        "[out:json][timeout:60];"
        f'nwr["addr:street"="{street.street}"]["addr:housenumber"]'
        f"({south:.3f},{west:.3f},{north:.3f},{east:.3f});"
        "out center tags;"
    )
    raw = _cached(
        f"osm-{street.export_id}.json",
        f"{OVERPASS}?{urllib.parse.urlencode({'data': query})}",
    )
    addresses = {}
    # здание перекрывает точку-адрес с тем же номером
    for element in sorted(
        json.loads(raw)["elements"], key=lambda element: "building" in element["tags"]
    ):
        center = element.get("center", element)
        addresses[house_number(element["tags"]["addr:housenumber"])] = (
            f"{center['lat']:.7f}",
            f"{center['lon']:.7f}",
        )
    for house in missing:
        house["lat"], house["lon"] = osm_match(
            house_number(str(house["building"])), addresses
        )
        if not house["lat"]:
            log.info("нет координат у %s, %s", street.street, house["building"])


def osm_match(number: str, addresses: dict[str, tuple[str, str]]) -> tuple[str, str]:
    # Реформа пишет корпус казанских домов через дробь (15/1), OSM - «15 к1».
    # Корпуса или строения, которого в OSM нет, ближайшая известная точка -
    # голый номер того же комплекса: от десятков метров до сотни
    for candidate in (number, number.replace("/", "к"), re.sub(r"\D.*", "", number)):
        if candidate in addresses:
            return addresses[candidate]
    return "", ""


if __name__ == "__main__":
    main()
