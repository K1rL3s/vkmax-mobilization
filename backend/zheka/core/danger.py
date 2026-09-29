import re

from zheka.base import ZhekaType
from zheka.core.enums import DangerKind

PHRASE_LIMIT = 60

_PARTS = re.compile(r"[,.!?;]| но ")
_NEGATED = re.compile(r"\b(?:не|нет|без|ни)\s+(?:\w+\s+)?$")
_ELSEWHERE = re.compile(
    r"\bдом\w*\s+напротив|напротив\s+(?:\w+\s+)?дом|\bсоседн\w*\s+дом"
    r"|через дорогу|в другом доме|по телевизору|в новостях",
)
_BURNS = r"(?:за)?гор(?:ит|ят|ел|ела|ело|ели|елся|елась|елось|ится)\b"
_LIGHT = re.compile(r"свет|ламп|фонар|индикатор")
_WIRING = re.compile(r"провод|щит|дым")
_RULES: tuple[tuple[DangerKind, str, str | None, bool], ...] = (
    (
        DangerKind.GAS,
        r"\b(?:пахн|запах|утечк|воня|тянет)\w*",
        r"\bгаз(?!он|ет|ел)\w*",
        True,
    ),
    (
        DangerKind.FIRE,
        (
            r"\b(?:дым(?!оход)\w*|задымл\w*|гар(?:ь|ью|и)\b|пожар(?!н)\w*"
            rf"|пламя|ого?н(?:ь|я|ем)\b|{_BURNS})"
        ),
        None,
        True,
    ),
    (
        DangerKind.FLOOD_ELECTRIC,
        r"\b(?:вод(?:а|ы|у|ой|е)\b|зали\w*|затоп\w*|теч\w*|протек\w*|капа\w*)",
        r"\b(?:щит|розетк|провод|электрощит)\w*",
        True,
    ),
    (
        DangerKind.ELECTRIC,
        (
            r"\b(?:искр(?!енн|енен)\w*|коротит|замыкан\w*|бь(?:ет|ют) током"
            r"|ударил\w* током|оголен\w*\s+провод\w*|провод\w*\s+оголен\w*)"
        ),
        None,
        True,
    ),
    (DangerKind.TRAPPED, r"\bзастрял\w*", r"\bлифт\w*", False),
)


class Danger(ZhekaType):
    kind: DangerKind
    phrase: str


def detect_danger(text: str) -> Danger | None:
    normalized = text.lower().replace("ё", "е")
    parts = [part for part in _PARTS.split(normalized) if not _ELSEWHERE.search(part)]
    for kind, trigger, context, same_part in _RULES:
        for part in parts:
            for found in re.finditer(trigger, part):
                if _NEGATED.search(part[: found.start()]) or _is_light(part, found):
                    continue
                start, end = found.span()
                if context is not None:
                    near = re.search(context, part)
                    if near is None and (
                        same_part or not re.search(context, normalized)
                    ):
                        continue
                    if near is not None:
                        start, end = min(start, near.start()), max(end, near.end())
                phrase = part[start:end] if end - start <= PHRASE_LIMIT else found[0]
                return Danger(kind=kind, phrase=phrase)
    return None


def _is_light(part: str, found: re.Match[str]) -> bool:
    return bool(
        re.fullmatch(_BURNS, found[0])
        and _LIGHT.search(part)
        and not _WIRING.search(part),
    )
