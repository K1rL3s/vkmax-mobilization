from datetime import timedelta
from enum import StrEnum


class HouseState(StrEnum):
    EMERGENCY = "emergency"
    ESCALATED = "escalated"
    OVERDUE = "overdue"
    OPEN = "open"
    CALM = "calm"


class MapPeriod(StrEnum):
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    HALF = "half"

    @property
    def span(self) -> timedelta:
        return timedelta(days=_DAYS[self])


_DAYS = {
    MapPeriod.WEEK: 7,
    MapPeriod.MONTH: 30,
    MapPeriod.QUARTER: 91,
    MapPeriod.HALF: 182,
}
