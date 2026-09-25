from dataclasses import field
from datetime import date, datetime
from typing import Any

from zheka.base import UNSET, ZhekaMutableType
from zheka.core.enums import MeterType
from zheka.core.ids import FlatId, MeterId, ReadingId, UserId


class Meter(ZhekaMutableType):
    id: MeterId = UNSET
    flat_id: FlatId
    type: MeterType
    tariff_zones: int = 1
    serial: str
    next_verification_date: date | None = None
    verification_warned_at: date | None = None


class Reading(ZhekaMutableType):
    id: ReadingId = UNSET
    meter_id: MeterId
    period: date
    values: Any
    photo_paths: Any = field(default_factory=list)
    ocr_used: bool
    ocr_accepted: bool
    is_below_previous: bool
    submitted_at: datetime
    submitted_by: UserId
