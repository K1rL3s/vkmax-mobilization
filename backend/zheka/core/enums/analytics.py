from enum import StrEnum


class MetricUnit(StrEnum):
    COUNT = "count"
    PERCENT = "percent"
    MINUTES = "minutes"
    KOPECK = "kopeck"
    POINTS = "points"


class AnalyticsMetric(StrEnum):
    ACCEPT_TIME = "accept_time"
    OVERDUE_SHARE = "overdue_share"
    REPEAT_SHARE = "repeat_share"
    AUTO_CLOSED_SHARE = "auto_closed_share"
    DIGITAL_SHARE = "digital_share"
    RATING = "rating"
