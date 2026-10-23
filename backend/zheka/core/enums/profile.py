from enum import StrEnum


class TextSize(StrEnum):
    NORMAL = "normal"
    LARGE = "large"
    XLARGE = "xlarge"


class Theme(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"
