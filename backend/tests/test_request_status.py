import pytest

from zheka.core.enums import RequestActorRole, RequestStatus
from zheka.core.errors import InvalidState
from zheka.core.services.request_status import (
    ALLOWED_TRANSITIONS,
    check_transition,
)

ORDER = (
    RequestStatus.NEW,
    RequestStatus.ACCEPTED,
    RequestStatus.IN_PROGRESS,
    RequestStatus.ON_REVIEW,
    RequestStatus.DONE,
)

# кто по цепочке имеет право поставить каждый следующий статус
FORWARD = (
    (RequestStatus.NEW, RequestStatus.ACCEPTED, RequestActorRole.STAFF),
    (RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS, RequestActorRole.EXECUTOR),
    (RequestStatus.IN_PROGRESS, RequestStatus.ON_REVIEW, RequestActorRole.EXECUTOR),
    (RequestStatus.ON_REVIEW, RequestStatus.DONE, RequestActorRole.RESIDENT),
)

BACKWARD = tuple(
    (current, target) for index, current in enumerate(ORDER) for target in ORDER[:index]
)


@pytest.mark.parametrize(("current", "target", "by_role"), FORWARD)
def test_every_forward_step_passes(
    current: RequestStatus,
    target: RequestStatus,
    by_role: RequestActorRole,
) -> None:
    check_transition(current, target, by_role, has_author=True)


@pytest.mark.parametrize(("current", "target"), BACKWARD)
def test_every_backward_step_raises(
    current: RequestStatus,
    target: RequestStatus,
) -> None:
    with pytest.raises(InvalidState):
        check_transition(current, target, RequestActorRole.STAFF, has_author=True)


@pytest.mark.parametrize("current", ORDER)
def test_a_status_never_moves_to_itself(current: RequestStatus) -> None:
    with pytest.raises(InvalidState):
        check_transition(current, current, RequestActorRole.STAFF, has_author=True)


def test_done_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS[RequestStatus.DONE] == frozenset()


def test_a_step_over_a_status_raises() -> None:
    # прыжок NEW -> В работе оставил бы заявку без строки «Принята», по
    # которой считается реакция УК
    with pytest.raises(InvalidState):
        check_transition(
            RequestStatus.NEW,
            RequestStatus.IN_PROGRESS,
            RequestActorRole.STAFF,
            has_author=True,
        )


def test_staff_cannot_close_a_request_that_has_an_author() -> None:
    # «Готово» от исполнителя не закрывает заявку, ее закрывает житель
    with pytest.raises(InvalidState):
        check_transition(
            RequestStatus.ON_REVIEW,
            RequestStatus.DONE,
            RequestActorRole.STAFF,
            has_author=True,
        )


def test_staff_closes_an_authorless_phone_request() -> None:
    # у заявки по звонку нет жителя, который нажмет «принято»
    check_transition(
        RequestStatus.ON_REVIEW,
        RequestStatus.DONE,
        RequestActorRole.STAFF,
        has_author=False,
    )


def test_executor_cannot_close_even_an_authorless_request() -> None:
    with pytest.raises(InvalidState):
        check_transition(
            RequestStatus.ON_REVIEW,
            RequestStatus.DONE,
            RequestActorRole.EXECUTOR,
            has_author=False,
        )


def test_scheduler_closes_a_request_left_on_review() -> None:
    check_transition(
        RequestStatus.ON_REVIEW,
        RequestStatus.DONE,
        RequestActorRole.SYSTEM,
        has_author=True,
    )


def test_resident_does_not_accept_a_request_for_the_management() -> None:
    with pytest.raises(InvalidState):
        check_transition(
            RequestStatus.NEW,
            RequestStatus.ACCEPTED,
            RequestActorRole.RESIDENT,
            has_author=True,
        )
