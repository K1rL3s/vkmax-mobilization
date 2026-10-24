from collections import defaultdict
from collections.abc import Mapping, Sequence

from zheka.base import ZhekaType
from zheka.core.enums import (
    HouseSystem,
    RequestCategory,
    RequestCompletionReason,
    RequestStatus,
)
from zheka.core.ids import RequestId
from zheka.core.models import Request

ELEVATOR_FROM_FLOORS = 6
SYSTEM_OF: Mapping[RequestCategory, HouseSystem] = {
    RequestCategory.ELEVATOR: HouseSystem.ELEVATOR,
    RequestCategory.WATER_SUPPLY: HouseSystem.WATER,
    RequestCategory.LEAK: HouseSystem.WATER,
    RequestCategory.HEATING: HouseSystem.HEATING,
    RequestCategory.ELECTRICITY: HouseSystem.ELECTRICITY,
    RequestCategory.GARBAGE: HouseSystem.GARBAGE,
    RequestCategory.ENTRANCE: HouseSystem.ENTRANCE,
    RequestCategory.YARD: HouseSystem.YARD,
}


class SystemHealth(ZhekaType):
    system: HouseSystem
    reported: int
    resolved: int
    open: int


def problem_key(
    request: Request,
    loaded: Mapping[RequestId, Request],
) -> tuple[str, int]:
    while request.group_id is None:
        parent_id = request.parent_request_id
        if parent_id is None:
            return "request", request.id
        if parent_id not in loaded:
            return "request", parent_id
        request = loaded[parent_id]
    return "group", request.group_id


def is_open(problem: Sequence[Request]) -> bool:
    return any(member.status is not RequestStatus.DONE for member in problem)


def is_resolved(problem: Sequence[Request]) -> bool:
    return not is_open(problem) and any(
        member.completion_reason
        in {
            RequestCompletionReason.RESIDENT_ACCEPTED,
            RequestCompletionReason.AUTO_CLOSED,
        }
        for member in problem
    )


def house_health(
    requests: Sequence[Request],
    *,
    with_elevator: bool,
) -> list[SystemHealth]:
    loaded = {request.id: request for request in requests}
    problems: dict[HouseSystem, dict[tuple[str, int], list[Request]]] = defaultdict(
        lambda: defaultdict(list),
    )
    for request in requests:
        system = SYSTEM_OF.get(request.category)
        if system is not None:
            problems[system][problem_key(request, loaded)].append(request)
    return [
        SystemHealth(
            system=system,
            reported=len(problems[system]),
            resolved=sum(map(is_resolved, problems[system].values())),
            open=sum(map(is_open, problems[system].values())),
        )
        for system in HouseSystem
        if with_elevator or system is not HouseSystem.ELEVATOR
    ]
