from zheka.core.enums import NotificationLevel

DEFAULT_LEVEL = NotificationLevel.SILENT


def resolve_notify(level: NotificationLevel, *, mandatory: bool) -> bool | None:
    if level is NotificationLevel.OFF and not mandatory:
        return None
    return level is NotificationLevel.SOUND
