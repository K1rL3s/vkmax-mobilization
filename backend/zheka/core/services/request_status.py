from collections.abc import Mapping
from types import MappingProxyType

from zheka.core.enums import RequestActorRole, RequestStatus
from zheka.core.errors import InvalidState

BACKWARD = "Статус заявки назад не двигается"
STAFF_CANNOT_CLOSE = "«Готово» от исполнителя не закрывает заявку, ее закрывает житель"
ROLE_CANNOT = "Этот статус ставит не ваша роль"

# цепочка из docs/zheka-mvp.md, раздел A: шаг вперед и только один. Прыжок
# через статус запрещен так же, как возврат назад - иначе у заявки нет истории,
# по которой считается норматив
ALLOWED_TRANSITIONS: Mapping[RequestStatus, frozenset[RequestStatus]] = (
    MappingProxyType(
        {
            RequestStatus.NEW: frozenset({RequestStatus.ACCEPTED}),
            RequestStatus.ACCEPTED: frozenset({RequestStatus.IN_PROGRESS}),
            RequestStatus.IN_PROGRESS: frozenset({RequestStatus.ON_REVIEW}),
            RequestStatus.ON_REVIEW: frozenset({RequestStatus.DONE}),
            RequestStatus.DONE: frozenset(),
        }
    )
)

# кто ставит каждый статус. DONE разобран отдельно: его ставит житель приемкой
# или планировщик по таймауту, а сотрудник - только у заявки без автора
_ROLES_BY_TARGET: Mapping[RequestStatus, frozenset[RequestActorRole]] = (
    MappingProxyType(
        {
            # исполнитель, которому назначили NEW, принимает ее сам
            RequestStatus.ACCEPTED: frozenset(
                {RequestActorRole.STAFF, RequestActorRole.EXECUTOR},
            ),
            RequestStatus.IN_PROGRESS: frozenset(
                {RequestActorRole.STAFF, RequestActorRole.EXECUTOR},
            ),
            RequestStatus.ON_REVIEW: frozenset(
                {RequestActorRole.STAFF, RequestActorRole.EXECUTOR},
            ),
            RequestStatus.DONE: frozenset(
                {RequestActorRole.RESIDENT, RequestActorRole.SYSTEM},
            ),
        }
    )
)


def check_transition(
    current: RequestStatus,
    target: RequestStatus,
    by_role: RequestActorRole,
    *,
    has_author: bool,
) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidState(BACKWARD)

    allowed = _ROLES_BY_TARGET[target]
    if by_role in allowed:
        return
    # заявка по звонку - единственная, у которой нет жителя, способного
    # принять работу, поэтому ее закрывает УК
    if (
        target is RequestStatus.DONE
        and by_role is RequestActorRole.STAFF
        and not has_author
    ):
        return
    if target is RequestStatus.DONE:
        raise InvalidState(STAFF_CANNOT_CLOSE)
    raise InvalidState(ROLE_CANNOT)


def transition_path(
    current: RequestStatus,
    target: RequestStatus,
) -> tuple[RequestStatus, ...]:
    # по одному шагу вперед; пустой путь - уже там, цель позади - InvalidState
    path: list[RequestStatus] = []
    step = current
    while step is not target:
        options = ALLOWED_TRANSITIONS[step]
        if not options:
            raise InvalidState(BACKWARD)
        step = next(iter(options))
        path.append(step)
    return tuple(path)
