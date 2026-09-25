from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, dataclass_transform
from zoneinfo import ZoneInfo

UNSET: Any = None

_FROZEN_ATTR = "__zheka_frozen__"
_SLOTS_ATTR = "__zheka_slots__"


@dataclass_transform(frozen_default=True, kw_only_default=True)
class _ZhekaTypeMetaClass(type):
    def __new__(
        cls,
        name: str,
        bases: tuple[Any, ...],
        namespace: dict[str, Any],
        frozen: bool | None = None,
        slots: bool | None = None,
        **kwargs: Any,
    ) -> Any:
        class_ = super().__new__(cls, name, bases, namespace, **kwargs)

        if frozen is None:
            frozen = getattr(class_, _FROZEN_ATTR, True)
        if slots is None:
            slots = getattr(class_, _SLOTS_ATTR, True)

        setattr(class_, _FROZEN_ATTR, frozen)
        setattr(class_, _SLOTS_ATTR, slots)

        if "__slots__" in namespace:
            return class_

        return dataclass(slots=slots, frozen=frozen, kw_only=True)(class_)


@dataclass_transform(frozen_default=False, kw_only_default=True)
class _ZhekaMutableTypeMetaClass(_ZhekaTypeMetaClass):
    pass


class ZhekaType(metaclass=_ZhekaTypeMetaClass):
    __slots__ = ()


class ZhekaMutableType(metaclass=_ZhekaMutableTypeMetaClass, frozen=False, slots=False):
    __slots__ = ()


class Zoned:
    __slots__ = ()

    timezone: str

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def local(self, moment: datetime) -> datetime:
        return moment.astimezone(self.zone)

    def day_start(self, day: date) -> datetime:
        return datetime.combine(day, time(), self.zone)

    def to_utc(self, moment: datetime) -> datetime:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=self.zone)
        return moment.astimezone(UTC)
