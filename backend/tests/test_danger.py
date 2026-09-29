import pytest

from zheka.core.danger import Danger, detect_danger
from zheka.core.enums import DangerKind


@pytest.mark.parametrize(
    ("text", "kind", "phrase"),
    [
        ("пахнет газом в подъезде", DangerKind.GAS, "пахнет газом"),
        ("Пахнет газом", DangerKind.GAS, "пахнет газом"),
        ("Газом воняет на кухне", DangerKind.GAS, "газом воняет"),
        (
            "Запах в подъезде стоит уже третий день и никто не проверил газовую трубу",
            DangerKind.GAS,
            "запах",
        ),
        ("в лифте застрял ребенок", DangerKind.TRAPPED, "лифте застрял"),
        ("застряли в лифте между 3 и 4", DangerKind.TRAPPED, "застряли в лифте"),
        ("не могу выйти из лифта, застрял", DangerKind.TRAPPED, "застрял"),
        ("дым из подвала", DangerKind.FIRE, "дым"),
        ("свет погас, но пахнет гарью", DangerKind.FIRE, "гарью"),
        ("горит проводка в щитке", DangerKind.FIRE, "горит"),
        ("искрит щиток на 5 этаже", DangerKind.ELECTRIC, "искрит"),
        ("Искрение в щитке на площадке", DangerKind.ELECTRIC, "искрение"),
        ("Бьёт током от ванны", DangerKind.ELECTRIC, "бьет током"),
        (
            "вода течет прямо в розетку",
            DangerKind.FLOOD_ELECTRIC,
            "вода течет прямо в розетку",
        ),
    ],
)
def test_a_dangerous_phrase_names_its_kind_and_words(
    text: str,
    kind: DangerKind,
    phrase: str,
) -> None:
    assert detect_danger(text) == Danger(kind=kind, phrase=phrase)


@pytest.mark.parametrize(
    "text",
    [
        "газом не пахнет, просто холодно",
        "Нет запаха газа",
        "в доме напротив пожар",
        "В доме напротив горит мусорка",
        "горит свет в подъезде весь день",
        "В третьем подъезде не горит свет на 5 этаже",
        "лифт не работает",
        "Лифт застревает между этажами",
        "течет кран",
        "Пахнет краской, газовую плиту поменяли",
        "плита газовая не зажигается",
        "пахнет скошенным газоном",
        "дымоход засорился",
        "пожарная сигнализация пищит",
        "Искренне благодарю электрика",
    ],
)
def test_a_calm_phrase_raises_no_alarm(text: str) -> None:
    assert detect_danger(text) is None
