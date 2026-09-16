from collections.abc import Sequence
from enum import StrEnum

from sqlalchemy import Enum


def _values(enum_cls: type[StrEnum]) -> Sequence[str]:
    return [member.value for member in enum_cls]


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    return Enum(enum_cls, name=name, values_callable=_values)
