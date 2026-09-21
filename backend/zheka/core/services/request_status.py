from zheka.core.enums import RequestActorRole, RequestStatus
from zheka.core.errors import InvalidState

BACKWARD = "Статус заявки назад не двигается"
STAFF_CANNOT_CLOSE = "«Готово» от исполнителя не закрывает заявку, ее закрывает житель"
ROLE_CANNOT = "Этот статус ставит не ваша роль"

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
    if target is not RequestStatus.DONE:
        if by_role in {RequestActorRole.STAFF, RequestActorRole.EXECUTOR}:
            return
        raise InvalidState(ROLE_CANNOT)
    if by_role in {RequestActorRole.RESIDENT, RequestActorRole.SYSTEM}:
        return
    if by_role is RequestActorRole.STAFF and not has_author:
        return
    raise InvalidState(STAFF_CANNOT_CLOSE)


def transition_path(
    current: RequestStatus, target: RequestStatus
) -> tuple[RequestStatus, ...]:
    start, end = _CHAIN.index(current), _CHAIN.index(target)
    if end < start:
        raise InvalidState(BACKWARD)
    return _CHAIN[start + 1 : end + 1]
