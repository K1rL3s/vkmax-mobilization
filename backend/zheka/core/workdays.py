from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SATURDAY = 5
LAST_CALENDAR_YEAR = 2027
HOLIDAYS = frozenset(
    {
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
        (1, 5),
        (1, 6),
        (1, 7),
        (1, 8),
        (2, 23),
        (3, 8),
        (5, 1),
        (5, 9),
        (6, 12),
        (11, 4),
    },
)

NON_WORKING_WEEKDAYS = frozenset(
    {
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 7),
        date(2026, 1, 8),
        date(2026, 1, 9),
        date(2026, 2, 23),
        date(2026, 3, 9),
        date(2026, 5, 1),
        date(2026, 5, 11),
        date(2026, 6, 12),
        date(2026, 11, 4),
        date(2026, 12, 31),
        date(2027, 1, 1),
        date(2027, 1, 4),
        date(2027, 1, 5),
        date(2027, 1, 6),
        date(2027, 1, 7),
        date(2027, 1, 8),
        date(2027, 2, 22),
        date(2027, 2, 23),
        date(2027, 3, 8),
        date(2027, 5, 3),
        date(2027, 5, 10),
        date(2027, 6, 14),
        date(2027, 11, 4),
        date(2027, 11, 5),
        date(2027, 12, 31),
    },
)
WORKING_WEEKENDS = frozenset({date(2027, 2, 20)})


def is_working_day(day: date) -> bool:
    if day in WORKING_WEEKENDS:
        return True
    if day.weekday() >= SATURDAY:
        return False
    if day.year > LAST_CALENDAR_YEAR:
        return (day.month, day.day) not in HOLIDAYS
    return day not in NON_WORKING_WEEKDAYS


def working_days_end(created_at: datetime, zone: ZoneInfo, count: int) -> datetime:
    day = created_at.astimezone(zone).date()
    left = count
    while left:
        day += timedelta(days=1)
        if is_working_day(day):
            left -= 1
    return datetime.combine(day, time.max, zone)
