from typing import ClassVar


class ZhekaError(Exception):
    title: ClassVar[str] = "ZhekaError"

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.title = cls.__name__


class Unauthorized(ZhekaError):
    def __init__(self, message: str = "Требуется авторизация") -> None:
        super().__init__(message)


class NotEnoughRights(ZhekaError, PermissionError):
    def __init__(self, message: str = "Недостаточно прав") -> None:
        super().__init__(message)


class EntityNotFound(ZhekaError, LookupError):
    def __init__(self, message: str = "Сущность не найдена") -> None:
        super().__init__(message)


HOUSE_NOT_FOUND = "Дом не найден"
FLAT_NOT_FOUND = "Квартира не найдена"
REQUEST_NOT_FOUND = "Заявка не найдена"
GROUP_NOT_FOUND = "Группа заявок не найдена"
INVITE_NOT_FOUND = "Приглашение не найдено"


class InvalidValue(ZhekaError, ValueError):
    def __init__(self, message: str = "Некорректное значение") -> None:
        super().__init__(message)


class InvalidState(InvalidValue):
    def __init__(self, message: str = "Недопустимое состояние") -> None:
        super().__init__(message)


class InvalidRequest(ZhekaError):
    def __init__(self, message: str = "Некорректный запрос") -> None:
        super().__init__(message)
