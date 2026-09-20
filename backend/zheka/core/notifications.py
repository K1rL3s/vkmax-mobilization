from zheka.core.enums import NotificationLevel

# продуктовый дефолт: бот молчит, пока житель сам не включит звук
DEFAULT_LEVEL = NotificationLevel.SILENT


def resolve_notify(level: NotificationLevel, *, mandatory: bool) -> bool | None:
    # None - сообщение не отправляется вовсе; обязательное сообщение
    # транзакционно или ждет ответа, поэтому OFF гасит только звук
    if level is NotificationLevel.SOUND:
        return True
    if level is NotificationLevel.SILENT:
        return False
    return False if mandatory else None


# кнопка едет в задачу через редис, поэтому это пара text/url, а не объект
# maxo; экраны с колбэками живут в диалогах блока 15
Buttons = list[dict[str, str]]
