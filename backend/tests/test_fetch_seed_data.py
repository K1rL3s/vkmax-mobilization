import runpy
from pathlib import Path

import pytest

from tests.conftest import BACKEND_ROOT

SCRIPT = runpy.run_path(str(BACKEND_ROOT / "scripts" / "fetch_seed_data.py"))

CARD_WITH_CONTRACT = """
<tr><td>Домом управляет</td><td>ООО &quot;НЕГА-М&quot;</td></tr>
<tr><td>Дата начала управления</td><td>01.01.2016</td></tr>
<div>Количество подъездов, ед.</div><div>14</div>
"""
CARD_WITH_SERVICES = """
<tr><td>Домом управляет</td><td>ТСЖ &quot;Магистраль&quot;</td></tr>
<tr><td>Вид коммунальной услуги</td><td>Отопление</td></tr>
"""


def test_a_card_names_its_manager_in_both_layouts() -> None:
    assert SCRIPT["parse_card"](CARD_WITH_CONTRACT) == (14, 'ООО "НЕГА-М"')
    assert SCRIPT["parse_card"](CARD_WITH_SERVICES) == (None, 'ТСЖ "Магистраль"')


@pytest.mark.parametrize(
    ("raw", "area_code", "expected"),
    [
        ("8(495) 225-30-78", None, "+74952253078"),
        ("+7 (499) 243-07-27", None, "+74992430727"),
        ("(843) 202-28-08", "843", "+78432022808"),
        ("241-69-49", "812", "+78122416949"),
        ("2680339, 89063259121", "843", "+78432680339"),
        ("12345", "812", ""),
    ],
)
def test_a_registry_phone_is_dialable_or_empty(
    raw: str,
    area_code: str | None,
    expected: str,
) -> None:
    assert SCRIPT["phone"](raw, area_code) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Priem@uk-ran.ru", "priem@uk-ran.ru"),
        ("info@uk.ru, buh@uk.ru", "info@uk.ru"),
        ("нет почты", ""),
        ("Net@mail.ru", ""),
    ],
)
def test_a_registry_mail_is_writable_or_empty(raw: str, expected: str) -> None:
    assert SCRIPT["email"](raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("www.uk-ran.ru", "https://www.uk-ran.ru"),
        ("HTTPS://UK.ru/Docs/Ustav", "https://uk.ru/Docs/Ustav"),
        ("www.reformagkh.ru/myhouse", ""),
        ("my.dom.gosuslugi.ru", ""),
        ("https://reformagkh.ru.uk-kazan.ru", "https://reformagkh.ru.uk-kazan.ru"),
        ("www.uk-ran.ru, www.reformagkh.ru", "https://www.uk-ran.ru"),
        ("www.dom.mos,ru", ""),
        ("bars-monjf.tatar.ru", ""),
        ("Net@mail.ru", ""),
        ("-", ""),
    ],
)
def test_a_registry_site_skips_the_registry_itself(raw: str, expected: str) -> None:
    assert SCRIPT["site"](raw) == expected


def test_an_osm_address_matches_a_card_number() -> None:
    addresses = {
        "70": ("0", "0"),
        "70/11": ("1", "1"),
        "15": ("0", "0"),
        "15к1": ("2", "2"),
        "47": ("3", "3"),
        "47к2": ("4", "4"),
    }
    assert SCRIPT["osm_match"]("70/11", addresses) == ("1", "1")
    assert SCRIPT["osm_match"]("15/1", addresses) == ("2", "2")
    assert SCRIPT["osm_match"]("47к1", addresses) == ("3", "3")
    assert SCRIPT["osm_match"]("48", addresses) == ("", "")


def test_a_litera_is_dropped_in_both_spellings() -> None:
    assert SCRIPT["house_number"]("9А литБ") == "9а"
    assert SCRIPT["house_number"]("9А литера Б") == "9а"


def test_a_gis_passport_keeps_its_dates_and_drops_an_empty_class() -> None:
    detail = {
        "cadastreNumber": "78:10:0005549:3052",
        "deterioration": "30.5",
        "deteriorationDate": "01.08.2021",
        "houseCondition": {"houseCondition": "Аварийный"},
        "houseEnergyEfficiency": "Нет",
    }

    assert SCRIPT["parse_gis"]({"lastUpdateDate": "28.09.2026"}, detail) == {
        "cadastral_no": "78:10:0005549:3052",
        "wear": 3050,
        "wear_on": "2021-08-01",
        "condition": "Аварийный",
        "energy_class": "",
        "gis_on": "2026-09-28",
    }


def test_a_sound_house_with_zero_wear_has_neither_condition_nor_wear() -> None:
    detail = {
        "houseCondition": {"houseCondition": "Исправный"},
        "deterioration": "0",
        "deteriorationDate": "01.08.2021",
        "houseEnergyEfficiency": "B+",
    }

    passport = SCRIPT["parse_gis"]({}, detail)

    assert (passport["condition"], passport["wear"], passport["wear_on"]) == (
        "",
        "",
        "",
    )
    assert passport["energy_class"] == "B+"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("B++", "B++"),
        ("Е (Пониженный - приказ Минстроя №399/пр)", "E"),
        ("В+ (Высокий)", "B+"),
        ("не присвоен", ""),
        ("Нет", ""),
        ("", ""),
    ],
)
def test_an_unassigned_energy_class_is_empty(raw: str, expected: str) -> None:
    assert SCRIPT["energy_class"](raw) == expected


def test_a_cancelled_gis_record_never_stands_for_a_house() -> None:
    lookup = {
        "houseList": [
            {"house": {"code": "fias-1"}, "guid": "old", "status": "CANCELLED"},
            {"house": {"code": "fias-1"}, "guid": "new", "status": "APPROVED"},
            {"house": {"code": "fias-2"}, "guid": "gone", "status": "CANCELLED"},
        ],
    }

    found = SCRIPT["gis_houses"](lookup)

    assert {code: item["guid"] for code, item in found.items()} == {"fias-1": "new"}
    assert SCRIPT["gis_houses"](None) == {}


def test_a_wear_dated_after_the_gis_update_keeps_no_date() -> None:
    detail = {"deterioration": "26", "deteriorationDate": "01.01.2066"}

    passport = SCRIPT["parse_gis"]({"lastUpdateDate": "12.09.2026"}, detail)

    assert (passport["wear"], passport["wear_on"]) == (2600, "")


def test_a_broken_gis_answer_is_dropped_and_stops_the_gis_requests(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    urls: list[str] = []

    def captcha(url: str) -> bytes:
        urls.append(url)
        return b"<html>captcha</html>"

    script = SCRIPT["_gis_json"].__globals__
    monkeypatch.setitem(script, "CACHE_DIR", tmp_path)
    monkeypatch.setitem(script, "_get", captcha)
    monkeypatch.setitem(script, "_gis_blocked", False)

    assert SCRIPT["_gis_json"]("gis-1.json", "https://gis/1") is None
    assert SCRIPT["_gis_json"]("gis-2.json", "https://gis/2") is None
    assert urls == ["https://gis/1"]
    assert list(tmp_path.iterdir()) == []
