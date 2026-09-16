from enum import StrEnum


class NotificationCategory(StrEnum):
    REQUESTS = "requests"
    ANNOUNCEMENTS = "announcements"
    METERS = "meters"


class NotificationLevel(StrEnum):
    SOUND = "sound"
    SILENT = "silent"
    OFF = "off"
