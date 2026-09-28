from typing import ClassVar


class ZhekaError(Exception):
    message: ClassVar[str]

    def __init__(self, message: str | None = None) -> None:
        super().__init__(self.message if message is None else message)


class Unauthorized(ZhekaError):
    message = "Требуется авторизация"


class NotEnoughRights(ZhekaError):
    message = "Недостаточно прав"


class EntityNotFound(ZhekaError):
    message = "Сущность не найдена"


HOUSE_NOT_FOUND = "Дом не найден"
ORG_NOT_FOUND = "Организация не найдена"
FLAT_NOT_FOUND = "Квартира не найдена"
REQUEST_NOT_FOUND = "Заявка не найдена"
GROUP_NOT_FOUND = "Группа заявок не найдена"
INVITE_NOT_FOUND = "Приглашение не найдено"


class InvalidValue(ZhekaError, ValueError):
    message = "Некорректное значение"


class InvalidState(InvalidValue):
    message = "Недопустимое состояние"


class InvalidRequest(ZhekaError):
    message = "Некорректный запрос"


class TooManyRequests(ZhekaError):
    message = "Слишком много запросов, попробуйте позже"
