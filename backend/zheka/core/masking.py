import re

_RULES = tuple(
    (re.compile(pattern, re.IGNORECASE), placeholder)
    for pattern, placeholder in (
        (r"\b[\w.%+-]+@[\w.-]+\.[a-z]{2,}\b", "[EMAIL]"),
        (
            r"(?<!\d)(?:\+7|8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)",
            "[ТЕЛЕФОН]",
        ),
        (r"\b\d{3}-\d{2}-\d{2}\b", "[ТЕЛЕФОН]"),
        (r"(?<!\d)\d{8,}(?!\d)", "[НОМЕР]"),
        (
            r"\bкв(?:\.|артир[аеуы])?\s*(?:(?:№|номер)\s*)?\d{1,4}[а-я]?\b",
            "[КВАРТИРА]",
        ),
        (r"\b\d{1,4}(?:-?[а-я]{1,3})?\s+квартир[аеуы]\b", "[КВАРТИРА]"),
    )
)


def mask_pii(text: str) -> str:
    for pattern, placeholder in _RULES:
        text = pattern.sub(placeholder, text)
    return text
