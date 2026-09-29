from zheka.core.enums import NotificationCategory, NotificationLevel


def default_level(category: NotificationCategory) -> NotificationLevel:
    if category is NotificationCategory.DIGEST:
        return NotificationLevel.OFF
    return NotificationLevel.SILENT
