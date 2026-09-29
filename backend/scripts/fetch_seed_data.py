import csv
import html
import io
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from math import ceil
from pathlib import Path
from typing import Any, NamedTuple

BACKEND_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = BACKEND_ROOT / ".cache" / "seed"
DATA_DIR = BACKEND_ROOT / "zheka" / "seed" / "data"

REFORMA = "https://www.reformagkh.ru"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"
GIS = "https://dom.gosuslugi.ru/homemanagement/api/rest/services/houses/public"
USER_AGENT = "zheka-seed-fetch/1.0 (MAX hackathon demo seed, one-off run)"
REQUEST_INTERVAL = 1.1
RETRIES = 5
RETRY_PAUSE = 30
TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500
REGISTRY_EXPORT = 1
BBOX_PAD = 0.01
HOUSES_PER_STREET = 55
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
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Дмитровское шоссе",
        prefix="Дмитровское шоссе ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Профсоюзная улица",
        prefix="Профсоюзная ул. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Каширское шоссе",
        prefix="Каширское шоссе ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Варшавское шоссе",
        prefix="Варшавское шоссе ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="проспект Мира",
        prefix="Мира просп. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Ленинградский проспект",
        prefix="Ленинградский просп. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Волгоградский проспект",
        prefix="Волгоградский просп. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Чертановская улица",
        prefix="Чертановская ул. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Дубнинская улица",
        prefix="Дубнинская ул. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Севастопольский проспект",
        prefix="Севастопольский просп. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=184,
        subject_rf="город Москва",
        region="Москва",
        city="Москва",
        street="Новокосинская улица",
        prefix="Новокосинская ул. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="Лиговский проспект",
        prefix="Лиговский пр., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="Московский проспект",
        prefix="Московский пр., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="проспект Стачек",
        prefix="Стачек пр., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="проспект Ветеранов",
        prefix="Ветеранов пр., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="Невский проспект",
        prefix="Невский пр., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="проспект Народного Ополчения",
        prefix="Народного Ополчения пр., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="Краснопутиловская улица",
        prefix="Краснопутиловская ул., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="бульвар Новаторов",
        prefix="Новаторов Бульвар, д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="улица Лёни Голикова",
        prefix="Лёни Голикова ул., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="улица Савушкина",
        prefix="Савушкина ул., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=250,
        subject_rf="город Санкт-Петербург",
        region="Санкт-Петербург",
        city="Санкт-Петербург",
        street="Садовая улица",
        prefix="Садовая ул., д. ",
        mun_obr="",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="улица Восстания",
        prefix="ул. Восстания, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="улица Рихарда Зорге",
        prefix="ул. Рихарда Зорге, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="улица Юлиуса Фучика",
        prefix="ул. Юлиуса Фучика, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="проспект Хусаина Ямашева",
        prefix="пр-кт. Ямашева, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="улица Маршала Чуйкова",
        prefix="ул. Маршала Чуйкова, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="улица Фатыха Амирхана",
        prefix="ул. Фатыха Амирхана, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="улица Адоратского",
        prefix="ул. Адоратского, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="проспект Ибрагимова",
        prefix="пр-кт. Ибрагимова, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="улица Декабристов",
        prefix="ул. Декабристов, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="улица Космонавтов",
        prefix="ул. Космонавтов, д. ",
        mun_obr="г. Казань",
        timezone="Europe/Moscow",
    ),
    Street(
        export_id=220,
        subject_rf="Республика Татарстан",
        region="Республика Татарстан",
        city="Казань",
        street="Чистопольская улица",
        prefix="ул. Чистопольская, д. ",
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
    "fias_guid",
    "entrances_estimated",
    "reforma_on",
    "energy_class",
    "cadastral_no",
    "wear",
    "wear_on",
    "condition",
    "gis_on",
)
NO_ENERGY_CLASS = {"", "не присвоен", "нет"}
LATIN_CLASSES = str.maketrans("АВСЕ", "ABCE")
ORG_FIELDS = ("inn", "name", "phone", "address", "email", "site", "timezone")
FULL_DIGITS = 11
LOCAL_DIGITS = 7
AREA_CODES = {"город Санкт-Петербург": "812", "Республика Татарстан": "843"}

_last_request = 0.0
_cards_blocked = False
_gis_blocked = False


def _get(url: str) -> bytes:
    global _last_request  # noqa: PLW0603
    wait = _last_request + REQUEST_INTERVAL - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    request = urllib.request.Request(url, headers=headers)  # noqa: S310
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
                return bytes(response.read())
        except (urllib.error.URLError, TimeoutError) as error:
            if (
                isinstance(error, urllib.error.HTTPError)
                and error.code != TOO_MANY_REQUESTS
                and error.code < SERVER_ERROR
            ):
                raise
            if attempt == RETRIES - 1:
                raise
            log.info("%s, повтор через %s с", error, RETRY_PAUSE)
            time.sleep(RETRY_PAUSE)
        finally:
            _last_request = time.monotonic()
    raise AssertionError


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
    exported_on = iso_date(name.removesuffix(".csv")[-8:], "%Y%m%d")
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        yield {**row, "exported_on": exported_on}


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", DASHES.sub("-", value)).strip()


def _scaled(value: str, scale: int) -> int:
    return int(Decimal(value.replace(",", ".")) * scale)


def _building_key(building: str) -> tuple[int, str]:
    match = re.match(r"\d+", building)
    return (int(match.group()) if match else 0, building)


def _card(source_id: str) -> tuple[int | None, str | None]:
    global _cards_blocked  # noqa: PLW0603
    name = f"card-{source_id}.html"
    if _cards_blocked and not (CACHE_DIR / name).exists():
        return None, None
    try:
        page = _cached(name, f"{REFORMA}/myhouse/profile/view/{source_id}").decode(
            "utf-8",
        )
    except urllib.error.URLError as error:
        log.info("карточки недоступны до конца прогона: %s", error)
        _cards_blocked = True
        return None, None
    entrances, manager = parse_card(page)
    if manager is None and "Домом управляет" in page:
        log.info("карточка %s называет УК, но имя не разобрано", source_id)
    return entrances, manager


def parse_card(page: str) -> tuple[int | None, str | None]:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
    entrances = re.search(r"Количество подъездов, ед\. (\d+)", text)
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
        },
    )
    safe = re.sub(r"\W+", "_", query)
    found = json.loads(_cached(f"geo-{safe}.json", f"{NOMINATIM}?{params}"))
    if not found or (
        house_number(found[0].get("address", {}).get("house_number", "")) != number
    ):
        return "", ""
    return found[0]["lat"], found[0]["lon"]


def _pick(street: Street) -> list[dict[str, str]]:
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
        "email": email(row["email"]),
        "site": site(row["site"]),
        "timezone": timezone,
    }


def email(value: str) -> str:
    first = _clean(re.split(r"[,;\s]", value, maxsplit=1)[0]).lower()
    return first if re.fullmatch(r"(?!net@)[^@\s]+@[^@\s]+\.[^@\s]+", first) else ""


def site(value: str) -> str:
    first = _clean(re.split(r"[;\s]", value, maxsplit=1)[0]).rstrip(",")
    if not first:
        return ""
    if not re.match(r"https?://", first, re.IGNORECASE):
        first = f"https://{first}"
    parts = urllib.parse.urlsplit(first.replace(" ", ""))
    host = parts.netloc.lower()
    known = ("reformagkh.ru", "dom.mos.ru", "dom.gosuslugi.ru", "bars-monjf.tatar.ru")
    if (
        "." not in host
        or re.search(r"[@,]", host)
        or any(host == domain or host.endswith(f".{domain}") for domain in known)
    ):
        return ""
    return urllib.parse.urlunsplit(
        parts._replace(scheme=parts.scheme.lower(), netloc=host),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    registry = _registry()

    houses = []
    orgs: dict[str, dict[str, str]] = {}
    for street in STREETS:
        street_houses: list[dict[str, str | int]] = []
        picked = _pick(street)
        found = _gis_lookup(street, [row["houseguid"] for row in picked])
        for row in picked:
            building = _clean(row["address"][len(street.prefix) :])
            building = building.replace(", корп.", " корп.").replace(
                ", литера",
                " литера",
            )
            entrances, manager = _card(row["house_id"])
            floors = int(row["number_floors_max"])
            living_flats = int(row["living_rooms_amount"])
            entrances_estimated = not entrances
            if not entrances:
                entrances = max(1, ceil(living_flats / (floors * 4)))
                log.info("нет подъездов в карточке %s, оценка %s", building, entrances)
            org_inn = ""
            if manager is not None:
                matches = {
                    candidate["inn"]: candidate
                    for candidate in registry.get(
                        (street.subject_rf, manager.lower()),
                        [],
                    )
                }
                if len(matches) == 1:
                    ((org_inn, org),) = matches.items()
                    orgs[org_inn] = _org(org, street.timezone)
                else:
                    log.info(
                        "УК %r у %s: совпадений %s",
                        manager,
                        building,
                        len(matches),
                    )
            lat, lon = _geocode(street, building)
            gis = _gis(found.get(row["houseguid"]))
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
                    "fias_guid": row["houseguid"],
                    "entrances_estimated": int(entrances_estimated),
                    "reforma_on": row["exported_on"],
                    **gis,
                    "energy_class": gis.get("energy_class")
                    or energy_class(row["energy_efficiency"]),
                },
            )
        _fill_from_osm(street, street_houses)
        houses.extend(street_houses)

    with (DATA_DIR / "houses.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, HOUSE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(houses)
    with (DATA_DIR / "organizations.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(file, ORG_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(orgs.values(), key=lambda org: org["inn"]))
    log.info(
        "домов %s, с координатами %s, с УК %s, из ГИС ЖКХ %s, организаций %s",
        len(houses),
        sum(1 for house in houses if house["lat"]),
        sum(1 for house in houses if house["org_inn"]),
        sum(1 for house in houses if house.get("gis_on")),
        len(orgs),
    )


def phone(value: str, area_code: str | None) -> str:
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
    query = (
        "[out:json][timeout:60];"
        f'nwr["addr:street"="{street.street}"]["addr:housenumber"]'
        f"({south:.3f},{west:.3f},{north:.3f},{east:.3f});"
        "out center tags;"
    )
    raw = _cached(
        f"osm-{street.export_id}-{street.street}.json",
        f"{OVERPASS}?{urllib.parse.urlencode({'data': query})}",
    )
    addresses = {}
    for element in sorted(
        json.loads(raw)["elements"],
        key=lambda element: "building" in element["tags"],
    ):
        center = element.get("center", element)
        addresses[house_number(element["tags"]["addr:housenumber"])] = (
            f"{center['lat']:.7f}",
            f"{center['lon']:.7f}",
        )
    for house in missing:
        house["lat"], house["lon"] = osm_match(
            house_number(str(house["building"])),
            addresses,
        )
        if not house["lat"]:
            log.info("нет координат у %s, %s", street.street, house["building"])


def osm_match(number: str, addresses: dict[str, tuple[str, str]]) -> tuple[str, str]:
    for candidate in (number, number.replace("/", "к"), re.sub(r"\D.*", "", number)):
        if candidate in addresses:
            return addresses[candidate]
    return "", ""


def energy_class(value: str) -> str:
    value = _clean(value).split(" (")[0].translate(LATIN_CLASSES)
    return "" if value.lower() in NO_ENERGY_CLASS else value


def iso_date(value: str | None, pattern: str = "%d.%m.%Y") -> str:
    return datetime.strptime(value, pattern).date().isoformat() if value else ""


def _gis_lookup(street: Street, guids: list[str]) -> dict[str, dict[str, Any]]:
    codes = ",".join(guid for guid in guids if guid)
    return gis_houses(
        _gis_json(
            f"gis-{street.export_id}-{street.street}.json",
            f"{GIS}/houses/searchByFiasHouseCodeList/{codes}"
            "?useReadOnlyDataSource=true",
        ),
    )


def _gis(found: dict[str, Any] | None) -> dict[str, str | int]:
    if found is None:
        return {}
    detail = _gis_json(
        f"gis-{found['guid']}.json",
        f"{GIS}/{found['houseType']['code']}/{found['guid']}",
    )
    return {} if detail is None else parse_gis(found, detail)


def _gis_json(name: str, url: str) -> Any:
    global _gis_blocked  # noqa: PLW0603
    if _gis_blocked and not (CACHE_DIR / name).exists():
        return None
    try:
        return json.loads(_cached(name, url))
    except (OSError, ValueError) as error:
        log.info("ГИС ЖКХ недоступна до конца прогона: %s", error)
        (CACHE_DIR / name).unlink(missing_ok=True)
        _gis_blocked = True
        return None


def parse_gis(found: dict[str, Any], detail: dict[str, Any]) -> dict[str, str | int]:
    condition = (detail.get("houseCondition") or {}).get("houseCondition") or ""
    wear = _scaled(detail.get("deterioration") or "0", 100)
    wear_on = iso_date(detail.get("deteriorationDate")) if wear else ""
    updated_on = iso_date(found.get("lastUpdateDate"))
    return {
        "cadastral_no": _clean(detail.get("cadastreNumber") or ""),
        "wear": wear or "",
        "wear_on": wear_on if wear_on <= updated_on else "",
        "condition": "" if condition == "Исправный" else condition,
        "energy_class": energy_class(detail.get("houseEnergyEfficiency") or ""),
        "gis_on": updated_on,
    }


def gis_houses(raw: Any) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for item in (raw or {}).get("houseList") or []:
        if item.get("status") != "CANCELLED":
            found.setdefault(item["house"]["code"], item)
    return found


if __name__ == "__main__":
    main()
