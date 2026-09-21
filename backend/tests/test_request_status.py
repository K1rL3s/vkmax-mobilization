import pytest

from zheka.core.enums import RequestActorRole as Role, RequestStatus as Status
from zheka.core.errors import InvalidState
from zheka.core.services.request_status import check_transition

ORDER = tuple(Status)

ALLOWED = (
    (Status.NEW, Status.ACCEPTED, Role.STAFF, True),
    (Status.NEW, Status.ACCEPTED, Role.EXECUTOR, True),
    (Status.ACCEPTED, Status.IN_PROGRESS, Role.EXECUTOR, True),
    (Status.IN_PROGRESS, Status.ON_REVIEW, Role.EXECUTOR, True),
    (Status.ON_REVIEW, Status.DONE, Role.RESIDENT, True),
    (Status.ON_REVIEW, Status.DONE, Role.SYSTEM, True),
    # у заявки по звонку нет жителя, который нажмет «принято»
    (Status.ON_REVIEW, Status.DONE, Role.STAFF, False),
)

# назад, на месте и через статус
OFF_CHAIN = tuple(
    (current, target)
    for index, current in enumerate(ORDER)
    for target in ORDER
    if ORDER.index(target) != index + 1
)

WRONG_ROLE = (
    (Status.ON_REVIEW, Status.DONE, Role.STAFF, True),
    (Status.ON_REVIEW, Status.DONE, Role.EXECUTOR, False),
    (Status.NEW, Status.ACCEPTED, Role.RESIDENT, True),
)


@pytest.mark.parametrize(("current", "target", "by_role", "has_author"), ALLOWED)
def test_an_allowed_step_passes(
    current: Status,
    target: Status,
    by_role: Role,
    has_author: bool,
) -> None:
    check_transition(current, target, by_role, has_author=has_author)


@pytest.mark.parametrize(("current", "target"), OFF_CHAIN)
def test_a_step_off_the_chain_raises(current: Status, target: Status) -> None:
    with pytest.raises(InvalidState):
        check_transition(current, target, Role.STAFF, has_author=True)


@pytest.mark.parametrize(("current", "target", "by_role", "has_author"), WRONG_ROLE)
def test_a_role_that_does_not_set_the_status_raises(
    current: Status,
    target: Status,
    by_role: Role,
    has_author: bool,
) -> None:
    with pytest.raises(InvalidState):
        check_transition(current, target, by_role, has_author=has_author)
