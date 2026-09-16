from dataclasses import field
from datetime import date, datetime
from typing import Any, cast

from zheka.base import ZhekaMutableType
from zheka.core.enums import MeterType
from zheka.core.ids import FlatId, MeterId, ReadingId, UserId

_UNSET_METER_ID = cast(MeterId, None)
_UNSET_READING_ID = cast(ReadingId, None)


class Meter(ZhekaMutableType):
    id: MeterId = _UNSET_METER_ID
    flat_id: FlatId
    type: MeterType
    tariff_zones: int = 1
    serial: str
    next_verification_date: date | None = None


class Reading(ZhekaMutableType):
    id: ReadingId = _UNSET_READING_ID
    meter_id: MeterId
    period: date
    values: Any
    photo_paths: Any = field(default_factory=list)
    ocr_used: bool
    ocr_accepted: bool
    is_below_previous: bool
    submitted_at: datetime
    submitted_by: UserId
