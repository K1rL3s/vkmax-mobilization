import importlib.util
from types import ModuleType

import pytest

from tests.conftest import BACKEND_ROOT


def _script() -> ModuleType:
    # скрипт лежит вне пакета и запускается руками, поэтому грузится по пути
    path = BACKEND_ROOT / "scripts" / "fetch_seed_data.py"
    spec = importlib.util.spec_from_file_location("fetch_seed_data", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _script()

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
    assert SCRIPT.parse_card(CARD_WITH_CONTRACT) == (14, 'ООО "НЕГА-М"')
    assert SCRIPT.parse_card(CARD_WITH_SERVICES) == (None, 'ТСЖ "Магистраль"')


@pytest.mark.parametrize(
    ("raw", "area_code", "expected"),
    [
        ("8(495) 225-30-78", None, "+74952253078"),
        ("+7 (499) 243-07-27", None, "+74992430727"),
        ("(843) 202-28-08", "843", "+78432022808"),
        ("241-69-49", "812", "+78122416949"),
        ("2680339, 89063259121", "843", "+78432680339"),
        ("0", "843", ""),
        ("нет", "843", ""),
        ("12345", "812", ""),
    ],
)
def test_a_registry_phone_is_dialable_or_empty(
    raw: str, area_code: str | None, expected: str
) -> None:
    assert SCRIPT.phone(raw, area_code) == expected


def test_an_osm_address_matches_a_card_number() -> None:
    addresses = {
        "70": ("0", "0"),
        "70/11": ("1", "1"),
        "15": ("0", "0"),
        "15к1": ("2", "2"),
        "47": ("3", "3"),
        "47к2": ("4", "4"),
    }
    assert SCRIPT.osm_match("70/11", addresses) == ("1", "1")
    assert SCRIPT.osm_match("15/1", addresses) == ("2", "2")
    assert SCRIPT.osm_match("47к1", addresses) == ("3", "3")
    assert SCRIPT.osm_match("48", addresses) == ("", "")


def test_a_litera_is_dropped_in_both_spellings() -> None:
    assert SCRIPT.house_number("9А литБ") == "9а"
    assert SCRIPT.house_number("9А литера Б") == "9а"
