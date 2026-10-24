import csv
import html
import io
import json
import logging
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
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
GIS_ORGS = "https://dom.gosuslugi.ru/ppa/api/rest/services/ppa/public/organizations"
USER_AGENT = "zheka-seed-fetch/1.0 (MAX hackathon demo seed, one-off run)"
REQUEST_INTERVAL = 1.5
HOST_INTERVALS = {
    "www.reformagkh.ru": 3.0,
    "nominatim.openstreetmap.org": 2.0,
    "overpass-api.de": 10.0,
}
RETRIES = 5
RETRY_PAUSE = 30
TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500
REGISTRY_EXPORT = 1
BBOX_PAD = 0.01
HOUSES_PER_STREET = 55
MAIN_CITIES = ("Москва", "Санкт-Петербург", "Казань")
ISO_REGIONS = {184: "RU-MOW", 250: "RU-SPE", 220: "RU-TA"}
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
    live: bool = False
    batch: int = 0

    @property
    def cache_name(self) -> str:
        if self.city in MAIN_CITIES:
            return f"{self.export_id}-{self.street}"
        return f"{self.export_id}-{self.city}-{self.street}"


KAZAN_STREETS = (
    ("улица Гагарина", "ул. Гагарина, д. "),
    ("улица Короленко", "ул. Короленко, д. "),
    ("улица Четаева", "ул. Четаева, д. "),
    ("Гвардейская улица", "ул. Гвардейская, д. "),
    ("улица Мира", "ул. Мира, д. "),
    ("Дубравная улица", "ул. Дубравная, д. "),
    ("улица Академика Глушко", "ул. Академика Глушко, д. "),
    ("Авангардная улица", "ул. Авангардная, д. "),
    ("улица Братьев Касимовых", "ул. Братьев Касимовых, д. "),
    ("улица Академика Королева", "ул. Академика Королева, д. "),
    ("Октябрьская улица", "ул. Октябрьская, д. "),
    ("улица Шамиля Усманова", "ул. Шамиля Усманова, д. "),
    ("улица Гаврилова", "ул. Гаврилова, д. "),
    ("улица Карбышева", "ул. Карбышева, д. "),
    ("улица Хусаина Мавлютова", "ул. Хусаина Мавлютова, д. "),
    ("улица Аделя Кутуя", "ул. Аделя Кутуя, д. "),
    ("улица Академика Губкина", "ул. Академика Губкина, д. "),
    ("Минская улица", "ул. Минская, д. "),
    ("улица Белинского", "ул. Белинского, д. "),
    ("улица Ноксинский Спуск", "ул. Ноксинский Спуск, д. "),
    ("улица Гудованцева", "ул. Гудованцева, д. "),
    ("улица Лукина", "ул. Лукина, д. "),
    ("Волгоградская улица", "ул. Волгоградская, д. "),
    ("улица Мусина", "ул. Мусина, д. "),
    ("улица Чапаева", "ул. Чапаева, д. "),
    ("Даурская улица", "ул. Даурская, д. "),
    ("улица Сафиуллина", "ул. Сафиуллина, д. "),
    ("Сибирский тракт", "тракт. Сибирский, д. "),
    ("улица Латышских Стрелков", "ул. Латышских Стрелков, д. "),
    ("улица Патриса Лумумбы", "ул. Патриса Лумумбы, д. "),
    ("улица Челюскина", "ул. Челюскина, д. "),
    ("улица Павлюхина", "ул. Павлюхина, д. "),
    ("улица Химиков", "ул. Химиков, д. "),
    ("улица Хайдара Бигичева", "ул. Хайдара Бигичева, д. "),
    ("улица Кулахметова", "ул. Кулахметова, д. "),
    ("Советская улица", "ул. Советская, д. "),
    ("улица Бондаренко", "ул. Бондаренко, д. "),
    ("улица Татарстан", "ул. Татарстан, д. "),
    ("улица Серова", "ул. Серова, д. "),
    ("улица Кул Гали", "ул. Кул Гали, д. "),
    ("улица Нурсултана Назарбаева", "ул. Нурсултана Назарбаева, д. "),
    ("улица Хади Такташа", "ул. Хади Такташа, д. "),
    ("Меридианная улица", "ул. Меридианная, д. "),
    ("улица Красной Позиции", "ул. Красной Позиции, д. "),
    ("Беломорская улица", "ул. Беломорская, д. "),
    ("Большая Красная улица", "ул. Большая Красная, д. "),
    ("Краснококшайская улица", "ул. Краснококшайская, д. "),
    ("улица Комиссара Габишева", "ул. Комиссара Габишева, д. "),
    ("Парковая улица", "ул. Парковая, д. "),
    ("улица Айдарова", "ул. Айдарова, д. "),
    ("улица Батыршина", "ул. Батыршина, д. "),
    ("Горьковское шоссе", "ш. Горьковское, д. "),
    ("улица Голубятникова", "ул. Голубятникова, д. "),
    ("улица Академика Завойского", "ул. Академика Завойского, д. "),
    ("улица Халезова", "ул. Халезова, д. "),
    ("Ленинградская улица", "ул. Ленинградская, д. "),
    ("улица Карла Маркса", "ул. Карла Маркса, д. "),
    ("улица Николая Ершова", "ул. Николая Ершова, д. "),
    ("улица Зур Урам", "ул. Зур Урам, д. "),
    ("улица Дементьева", "ул. Дементьева, д. "),
    ("Главная улица", "ул. Главная, д. "),
    ("улица Заря", "ул. Заря, д. "),
    ("улица Липатова", "ул. Липатова, д. "),
    ("Отрадная улица", "ул. Отрадная, д. "),
    ("улица Волкова", "ул. Волкова, д. "),
    ("улица Достоевского", "ул. Достоевского, д. "),
    ("улица Щапова", "ул. Щапова, д. "),
    ("улица Тунакова", "ул. Тунакова, д. "),
    ("улица Абсалямова", "ул. Абсалямова, д. "),
    ("улица Гарифьянова", "ул. Гарифьянова, д. "),
    ("улица Академика Сахарова", "ул. Академика Сахарова, д. "),
    ("Ломжинская улица", "ул. Ломжинская, д. "),
    ("улица Восход", "ул. Восход, д. "),
    ("улица Максимова", "ул. Максимова, д. "),
    ("Бирюзовая улица", "ул. Бирюзовая, д. "),
    ("улица Сыртлановой", "ул. Сыртлановой, д. "),
    ("улица Вишневского", "ул. Вишневского, д. "),
    ("улица Гоголя", "ул. Гоголя, д. "),
    ("улица Чехова", "ул. Чехова, д. "),
    ("улица Академика Лаврентьева", "ул. Академика Лаврентьева, д. "),
    ("улица Академика Кирпичникова", "ул. Академика Кирпичникова, д. "),
    ("улица Закиева", "ул. Закиева, д. "),
    ("улица Рашида Вагапова", "ул. Рашида Вагапова, д. "),
    ("улица Академика Павлова", "ул. Академика Павлова, д. "),
    ("улица Олега Кошевого", "ул. Олега Кошевого, д. "),
    ("улица Побежимова", "ул. Побежимова, д. "),
    ("улица Галимджана Баруди", "ул. Галимджана Баруди, д. "),
    ("улица Лейтенанта Красикова", "ул. Лейтенанта Красикова, д. "),
    ("улица Воровского", "ул. Воровского, д. "),
    ("Курская улица", "ул. Курская, д. "),
    ("улица Маяковского", "ул. Маяковского, д. "),
    ("улица Муштари", "ул. Муштари, д. "),
    ("улица Железнодорожников", "ул. Железнодорожников, д. "),
    ("Окольная улица", "ул. Окольная, д. "),
    ("Привокзальная улица", "ул. Привокзальная, д. "),
    ("Шоссейная улица", "ул. Шоссейная, д. "),
    ("Коломенская улица", "ул. Коломенская, д. "),
    ("улица Сибгата Хакима", "ул. Сибгата Хакима, д. "),
    ("улица Журналистов", "ул. Журналистов, д. "),
    ("улица Новаторов", "ул. Новаторов, д. "),
    ("улица Жуковского", "ул. Жуковского, д. "),
    ("2-я Юго-Западная улица", "ул. Юго-Западная 2-я, д. "),
    ("улица Курчатова", "ул. Курчатова, д. "),
    ("улица Карима Тинчурина", "ул. Карима Тинчурина, д. "),
    ("улица Можайского", "ул. Можайского, д. "),
    ("проспект Альберта Камалеева", "пр-кт. Альберта Камалеева, д. "),
    ("улица Галии Кайбицкой", "ул. Галии Кайбицкой, д. "),
    ("Каштановая улица", "ул. Каштановая, д. "),
    ("Ново-Азинская улица", "ул. Ново-Азинская, д. "),
    ("улица Лядова", "ул. Лядова, д. "),
    ("улица Заслонова", "ул. Заслонова, д. "),
    ("Спартаковская улица", "ул. Спартаковская, д. "),
    ("улица 40 лет Октября", "ул. 40 лет Октября, д. "),
    ("Залесная улица", "ул. Залесная, д. "),
    ("улица Ильича", "ул. Ильича, д. "),
    ("улица Лушникова", "ул. Лушникова, д. "),
    ("Осиновская улица", "ул. Осиновская, д. "),
    ("Революционная улица", "ул. Революционная, д. "),
    ("улица Академика Парина", "ул. Академика Парина, д. "),
    ("Начальная улица", "ул. Начальная, д. "),
    ("улица Бутлерова", "ул. Бутлерова, д. "),
    ("улица Зинина", "ул. Зинина, д. "),
    ("улица Некрасова", "ул. Некрасова, д. "),
    ("улица Наиля Юсупова", "ул. Наиля Юсупова, д. "),
    ("улица Сабан", "ул. Сабан, д. "),
    ("Светлая улица", "ул. Светлая, д. "),
    ("улица Фрунзе", "ул. Фрунзе, д. "),
    ("улица Хасана Туфана", "ул. Хасана Туфана, д. "),
    ("Хлебозаводская улица", "ул. Хлебозаводская, д. "),
    ("Безоблачная улица", "ул. Безоблачная, д. "),
    ("улица Профессора Камая", "ул. Профессора Камая, д. "),
    ("улица Рауиса Гареева", "ул. Рауиса Гареева, д. "),
    ("улица Салиха Батыева", "ул. Салиха Батыева, д. "),
    ("2-я Азинская улица", "ул. Азинская 2-я, д. "),
    ("2-я Даурская улица", "ул. Даурская 2-я, д. "),
    ("улица Джаудата Файзи", "ул. Джаудата Файзи, д. "),
)
MOSCOW_STREETS = (
    ("Южнобутовская улица", "Южнобутовская ул. "),
    ("Бескудниковский бульвар", "Бескудниковский бульв. "),
    ("Ленинградское шоссе", "Ленинградское шоссе "),
    ("Хорошёвское шоссе", "Хорошевское шоссе "),
    ("Первомайская улица", "Первомайская ул. "),
    ("улица Свободы", "Свободы ул. "),
)
SPB_STREETS = (
    ("набережная реки Фонтанки", "Фонтанки реки наб., д. "),
    ("Ленинский проспект", "Ленинский пр., д. "),
    ("Дачный проспект", "Дачный пр., д. "),
    ("улица Седова", "Седова ул., д. "),
    ("Будапештская улица", "Будапештская ул., д. "),
    ("улица Марата", "Марата ул., д. "),
)
LATER_STREETS = Path(__file__).with_name("later_streets.csv")
SUBJECTS = {
    184: ("город Москва", "Москва"),
    250: ("город Санкт-Петербург", "Санкт-Петербург"),
    220: ("Республика Татарстан", "Республика Татарстан"),
}


def _later_streets() -> Iterator[tuple[int, int, str, str, str, str]]:
    with LATER_STREETS.open(encoding="utf-8") as file:
        for row in csv.DictReader(file):
            yield (
                int(row["batch"]),
                int(row["export_id"]),
                row["city"],
                row["mun_obr"],
                row["street"],
                row["prefix"],
            )


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
    *(
        Street(
            export_id=220,
            subject_rf="Республика Татарстан",
            region="Республика Татарстан",
            city="Казань",
            street=street,
            prefix=prefix,
            mun_obr="г. Казань",
            timezone="Europe/Moscow",
            live=True,
        )
        for street, prefix in KAZAN_STREETS
    ),
    *(
        Street(
            export_id=184,
            subject_rf="город Москва",
            region="Москва",
            city="Москва",
            street=street,
            prefix=prefix,
            mun_obr="",
            timezone="Europe/Moscow",
            live=True,
        )
        for street, prefix in MOSCOW_STREETS
    ),
    *(
        Street(
            export_id=250,
            subject_rf="город Санкт-Петербург",
            region="Санкт-Петербург",
            city="Санкт-Петербург",
            street=street,
            prefix=prefix,
            mun_obr="",
            timezone="Europe/Moscow",
            live=True,
        )
        for street, prefix in SPB_STREETS
    ),
    *(
        Street(
            export_id=export_id,
            subject_rf=SUBJECTS[export_id][0],
            region=SUBJECTS[export_id][1],
            city=city,
            street=street,
            prefix=prefix,
            mun_obr=mun_obr,
            timezone="Europe/Moscow",
            live=True,
            batch=batch,
        )
        for batch, export_id, city, mun_obr, street, prefix in _later_streets()
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

_last_request: dict[str, float] = {}
_gis_blocked = False
_osm_failed: list[str] = []


def _get(url: str) -> bytes:
    host = urllib.parse.urlsplit(url).netloc
    interval = HOST_INTERVALS.get(host, REQUEST_INTERVAL)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    request = urllib.request.Request(url, headers=headers)  # noqa: S310
    for attempt in range(RETRIES):
        wait = _last_request.get(host, 0.0) + interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
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
            pause = RETRY_PAUSE * 2**attempt
            log.info("%s, повтор через %s с", error, pause)
            time.sleep(pause)
        finally:
            _last_request[host] = time.monotonic()
    raise AssertionError


def _cached(name: str, url: str) -> bytes:
    path = CACHE_DIR / name
    if not path.exists():
        log.info("GET %s", url)
        _store(path, _get(url))
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
    path = CACHE_DIR / f"card-{source_id}.html"
    if not path.exists():
        return None, None
    page = path.read_text(encoding="utf-8")
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
    if street.batch and not on_street(street, found[0].get("address", {})):
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
        and _is_number(row["total_sq"])
        and _is_number(row["living_rooms_sq"])
        and _is_number(row["owners_payment"])
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


def main(batch: int | None = None) -> None:
    if batch is None:
        batch = max(street.batch for street in STREETS)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    registry = _registry()
    by_ogrn = _registry_by_ogrn()
    kept_houses = _previous("houses.csv")
    kept_orgs = {org["inn"]: org for org in _previous("organizations.csv")}
    by_street: dict[Street, Sequence[Mapping[str, object]]] = {}
    orgs: dict[str, dict[str, str]] = {}
    for street in STREETS:
        if street.batch > batch:
            continue
        kept = [
            house
            for house in kept_houses
            if (house["city"], house["street"]) == (street.city, street.street)
        ]
        if kept and (not street.live or street.batch < batch):
            by_street[street] = kept
            orgs.update(
                (house["org_inn"], kept_orgs[house["org_inn"]])
                for house in kept
                if house["org_inn"]
            )
            continue
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
            gis, detail = _gis(found.get(row["houseguid"]))
            ogrn = gis_manager(detail)
            listed = None
            if manager is not None:
                listed = unique_org(
                    registry.get((street.subject_rf, manager.lower()), []),
                )
                if listed is None:
                    log.info("УК %r у %s не сопоставлена с реестром", manager, building)
            if street.live and listed is None and ogrn:
                listed = unique_org(by_ogrn.get(ogrn, []))
            org = None if listed is None else _org(listed, street.timezone)
            if street.live and org is None and ogrn:
                org = _gis_org(detail, street.timezone)
            if street.live and org is None and (manager or ogrn):
                log.info("УК дома %s не найдена по ИНН, дом пропущен", building)
                continue
            org_inn = ""
            if org is not None:
                org_inn = org["inn"]
                orgs.setdefault(org_inn, org)
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
                    "fias_guid": row["houseguid"],
                    "entrances_estimated": int(entrances_estimated),
                    "reforma_on": row["exported_on"],
                    **gis,
                    "energy_class": gis.get("energy_class")
                    or energy_class(row["energy_efficiency"]),
                },
            )
        _fill_from_osm(street, street_houses)
        by_street[street] = street_houses
        log.info("%s, %s: домов %s", street.city, street.street, len(street_houses))
    if _gis_blocked or _osm_failed:
        raise SystemExit("ГИС ЖКХ или Overpass отказали, CSV не записаны: повторите")
    houses = [house for street in by_street for house in by_street[street]]

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
    try:
        raw = _cached(
            f"osm-{street.cache_name}.json",
            f"{OVERPASS}?{urllib.parse.urlencode({'data': query})}",
        )
    except OSError as error:
        log.info("Overpass не ответил по %s: %s", street.street, error)
        _osm_failed.append(street.street)
        return
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
            f"gis-{street.cache_name}.json",
            f"{GIS}/houses/searchByFiasHouseCodeList/{codes}"
            "?useReadOnlyDataSource=true",
        ),
    )


def _gis(
    found: dict[str, Any] | None,
) -> tuple[dict[str, str | int], dict[str, Any]]:
    if found is None:
        return {}, {}
    detail = _gis_json(
        f"gis-{found['guid']}.json",
        f"{GIS}/{found['houseType']['code']}/{found['guid']}",
    )
    if detail is None:
        return {}, {}
    return parse_gis(found, detail), detail


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


def _store(path: Path, data: bytes) -> None:
    part = path.with_name(f"{path.name}.part")
    part.write_bytes(data)
    part.replace(path)


def _registry_by_ogrn() -> dict[str, list[dict[str, str]]]:
    by_ogrn: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _export_rows(REGISTRY_EXPORT):
        if row["orn"]:
            by_ogrn[row["orn"]].append(row)
    return by_ogrn


def _previous(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


def unique_org(candidates: list[dict[str, str]]) -> dict[str, str] | None:
    by_inn = {candidate["inn"]: candidate for candidate in candidates}
    return next(iter(by_inn.values())) if len(by_inn) == 1 else None


def gis_manager(detail: dict[str, Any]) -> str:
    return str((detail.get("managementOrganization") or {}).get("ogrn") or "")


def _gis_org(detail: dict[str, Any], timezone: str) -> dict[str, str] | None:
    guid = (detail.get("managementOrganization") or {}).get("guid")
    if not guid:
        return None
    path = CACHE_DIR / f"gis-org-{guid}.json"
    if not path.exists():
        if _gis_blocked:
            return None
        url = f"{GIS_ORGS}/orgByGuid?organizationGuid={guid}"
        log.info("GET %s", url)
        try:
            raw = _get(url)
            card = json.loads(raw)
        except (OSError, ValueError) as error:
            log.info("карточка УК %s из ГИС ЖКХ не получена: %s", guid, error)
            return None
        if not isinstance(card, dict) or not card.get("inn"):
            return None
        _store(path, raw)
    return gis_org(json.loads(path.read_bytes()), timezone)


def gis_org(card: dict[str, Any], timezone: str) -> dict[str, str]:
    return {
        "inn": str(card["inn"]),
        "name": _clean(card.get("shortName") or card.get("fullName") or ""),
        "phone": phone(str(card.get("phone") or ""), None),
        "address": _clean(card.get("orgAddress") or ""),
        "email": email(str(card.get("orgEmail") or "")),
        "site": site(str(card.get("url") or "")),
        "timezone": timezone,
    }


def on_street(street: Street, address: dict[str, str]) -> bool:
    road = re.sub(r" \(.*\)$", "", address.get("road", ""))
    return address.get("ISO3166-2-lvl4") == ISO_REGIONS[street.export_id] and (
        road.lower().replace("ё", "е") == street.street.lower().replace("ё", "е")
    )


def _is_number(value: str) -> bool:
    try:
        Decimal(value.replace(",", "."))
    except InvalidOperation:
        return False
    return True


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
