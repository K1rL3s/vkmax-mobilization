from enum import StrEnum


class NotificationCategory(StrEnum):
    REQUESTS = "requests"
    ANNOUNCEMENTS = "announcements"
    METERS = "meters"
    DIGEST = "digest"


class NotificationLevel(StrEnum):
    SOUND = "sound"
    SILENT = "silent"
    OFF = "off"

    def resolve_notify(self, *, mandatory: bool) -> bool | None:
        if self is NotificationLevel.OFF and not mandatory:
            return None
        return self is NotificationLevel.SOUND
