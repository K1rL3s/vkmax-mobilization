from zheka.core.enums import RequestActorRole, RequestStatus
from zheka.core.errors import InvalidState

BACKWARD = "Статус заявки назад не двигается"
STAFF_CANNOT_CLOSE = "«Готово» от исполнителя не закрывает заявку, ее закрывает житель"
ROLE_CANNOT = "Этот статус ставит не ваша роль"

# цепочка из docs/zheka-mvp.md, раздел A: шаг вперед и только один. Прыжок
# через статус запрещен так же, как возврат назад - иначе у заявки нет истории,
# по которой считается норматив
_CHAIN = (
    RequestStatus.NEW,
    RequestStatus.ACCEPTED,
    RequestStatus.IN_PROGRESS,
    RequestStatus.ON_REVIEW,
    RequestStatus.DONE,
)


def check_transition(
    current: RequestStatus,
    target: RequestStatus,
    by_role: RequestActorRole,
    *,
    has_author: bool,
) -> None:
    if _CHAIN.index(target) != _CHAIN.index(current) + 1:
        raise InvalidState(BACKWARD)
    # исполнитель, которому назначили NEW, принимает ее сам
    if target is not RequestStatus.DONE:
        if by_role in {RequestActorRole.STAFF, RequestActorRole.EXECUTOR}:
            return
        raise InvalidState(ROLE_CANNOT)
    # DONE ставит житель приемкой или планировщик по таймауту. Заявка по
    # звонку - единственная без жителя, способного принять работу, поэтому ее
    # закрывает УК
    if by_role in {RequestActorRole.RESIDENT, RequestActorRole.SYSTEM}:
        return
    if by_role is RequestActorRole.STAFF and not has_author:
        return
    raise InvalidState(STAFF_CANNOT_CLOSE)


def transition_path(
    current: RequestStatus, target: RequestStatus
) -> tuple[RequestStatus, ...]:
    # по одному шагу вперед; пустой путь - уже там, цель позади - InvalidState
    start, end = _CHAIN.index(current), _CHAIN.index(target)
    if end < start:
        raise InvalidState(BACKWARD)
    return _CHAIN[start + 1 : end + 1]
