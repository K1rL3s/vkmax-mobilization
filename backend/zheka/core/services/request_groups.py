from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timedelta

from zheka.base import ZhekaType
from zheka.core.enums import (
    CATEGORY_PLACES,
    ChatCardKind,
    EventType,
    RequestCategory,
    RequestCompletionReason,
    RequestPlace,
    RequestStatus,
)
from zheka.core.ids import FlatId, HouseId, RequestGroupId, UserId
from zheka.core.models import OrgSettings, Request
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.requests import RequestsRepo

DEFAULT_GROUP_THRESHOLD = 3
DEFAULT_GROUP_WINDOW_HOURS = 24
PRIVATE_CATEGORIES = frozenset(
    category
    for category, place in CATEGORY_PLACES.items()
    if place is RequestPlace.FLAT
)
RESOLVED_PERIOD = timedelta(days=30)
RESOLVED_SHOWN = 20


class GroupingRules(ZhekaType):
    threshold: int
    window_hours: int


class SimilarRequests(ZhekaType):
    category: RequestCategory
    flats_count: int
    group_id: RequestGroupId | None
    window_started_at: datetime | None


def rules_of(settings: OrgSettings | None) -> GroupingRules:
    if settings is None:
        return GroupingRules(
            threshold=DEFAULT_GROUP_THRESHOLD,
            window_hours=DEFAULT_GROUP_WINDOW_HOURS,
        )
    return GroupingRules(
        threshold=settings.group_threshold,
        window_hours=settings.group_window_hours,
    )


def complaint_sources(requests: Sequence[Request]) -> set[tuple[str, int]]:
    sources: set[tuple[str, int]] = set()
    for request in requests:
        if request.flat_id is not None:
            sources.add(("flat", request.flat_id))
        elif request.author_user_id is not None:
            sources.add(("user", request.author_user_id))
    return sources


class GroupingService:
    __slots__ = ("_events", "_notifications", "_requests")

    def __init__(
        self,
        requests_repo: RequestsRepo,
        events_service: EventsService,
        notifications_service: NotificationsService,
    ) -> None:
        self._requests = requests_repo
        self._events = events_service
        self._notifications = notifications_service

    async def attach(
        self,
        request: Request,
        rules: GroupingRules,
        now: datetime,
    ) -> None:
        if request.category in PRIVATE_CATEGORIES:
            return
        since = now - timedelta(hours=rules.window_hours)
        house_id = request.house_id
        group = await self._requests.find_open_group(house_id, request.category, since)
        if group is not None:
            await self._requests.attach_to_group([request], group.id)
            await self.joined(request, group.id)
            return

        open_requests = await self._requests.list_open_in_window(
            house_id,
            request.category,
            since,
        )
        if len(complaint_sources(open_requests)) < rules.threshold:
            return

        oldest = min(item.created_at for item in open_requests)
        group = await self._requests.create_group(house_id, request.category, oldest)
        await self._requests.attach_to_group(open_requests, group.id)
        for member in open_requests:
            self._notifications.sync_chat_card(
                ChatCardKind.REQUEST,
                member.id,
                post=False,
            )
        await self._events.record(
            EventType.REQUEST_GROUP_FORMED,
            user_id=request.author_user_id,
            house_id=house_id,
            category=request.category.value,
            size=len(open_requests),
        )
        self._notifications.sync_chat_card(ChatCardKind.GROUP, group.id, post=True)

    async def similar(
        self,
        house_id: HouseId,
        category: RequestCategory,
        rules: GroupingRules,
        now: datetime,
        exclude_flat_id: FlatId | None,
        exclude_user_id: UserId,
    ) -> SimilarRequests:
        if category in PRIVATE_CATEGORIES:
            return SimilarRequests(
                category=category,
                flats_count=0,
                group_id=None,
                window_started_at=None,
            )
        since = now - timedelta(hours=rules.window_hours)
        group = await self._requests.find_open_group(house_id, category, since)
        open_requests = await self._requests.list_open_in_window(
            house_id,
            category,
            since,
        )
        sources = complaint_sources(open_requests) - {
            ("flat", exclude_flat_id),
            ("user", exclude_user_id),
        }
        return SimilarRequests(
            category=category,
            flats_count=len(sources),
            group_id=None if group is None else group.id,
            window_started_at=(
                group.window_started_at
                if group is not None
                else min((item.created_at for item in open_requests), default=None)
            ),
        )

    async def joined(self, request: Request, group_id: RequestGroupId) -> None:
        sizes = await self._requests.count_by_group([group_id])
        await self._events.record(
            EventType.REQUEST_JOINED,
            user_id=request.author_user_id,
            request_id=request.id,
            group_id=group_id,
            group_size=sizes.get(group_id, 0),
        )
        self._notifications.sync_chat_card(ChatCardKind.GROUP, group_id, post=True)


class OpenProblem(ZhekaType):
    category: RequestCategory
    flats_count: int
    status: RequestStatus
    since: datetime
    mine: bool
    place: RequestPlace


class ResolvedProblem(ZhekaType):
    category: RequestCategory
    done_at: datetime
    confirmed: bool
    place: RequestPlace


class HouseProblems(ZhekaType):
    open: Sequence[OpenProblem]
    resolved: Sequence[ResolvedProblem]
    resolved_total: int


def problems_of(
    open_requests: Sequence[Request],
    done_requests: Sequence[Request],
    user_id: UserId,
    flat_id: FlatId | None,
) -> HouseProblems:
    shown = [
        request
        for request in open_requests
        if request.category not in PRIVATE_CATEGORIES
    ]
    problems: dict[tuple[RequestCategory, RequestGroupId | None], list[Request]] = (
        defaultdict(list)
    )
    for request in shown:
        problems[request.category, request.group_id].append(request)
    open_groups = {request.group_id for request in shown} - {None}
    finished: dict[tuple[str, int], list[Request]] = defaultdict(list)
    for request in done_requests:
        if request.category in PRIVATE_CATEGORIES or request.group_id in open_groups:
            continue
        if request.group_id is None:
            finished["request", request.id].append(request)
        else:
            finished["group", request.group_id].append(request)
    resolved = [
        ResolvedProblem(
            category=members[0].category,
            done_at=max(filter(None, (member.done_at for member in members))),
            confirmed=any(
                member.completion_reason is RequestCompletionReason.RESIDENT_ACCEPTED
                for member in members
            ),
            place=min(members, key=lambda member: member.id).place,
        )
        for members in finished.values()
    ]
    return HouseProblems(
        open=[
            OpenProblem(
                category=category,
                flats_count=max(len(complaint_sources(members)), 1),
                status=min(
                    (member.status for member in members),
                    key=list(RequestStatus).index,
                ),
                since=min(member.created_at for member in members),
                mine=any(
                    member.author_user_id == user_id
                    or (flat_id is not None and member.flat_id == flat_id)
                    for member in members
                ),
                place=min(members, key=lambda member: member.id).place,
            )
            for (category, _), members in problems.items()
        ],
        resolved=resolved[:RESOLVED_SHOWN],
        resolved_total=len(resolved),
    )
