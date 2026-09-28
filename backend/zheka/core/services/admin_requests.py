from collections.abc import Sequence
from datetime import UTC, datetime

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.deeplinks import admin_request_app_path
from zheka.core.enums import (
    EventType,
    NotificationCategory,
    OrgRole,
    RequestActorRole,
    RequestCategory,
    RequestChannel,
    RequestGroupStatus,
    RequestPhotoKind,
    RequestStatus,
    ResidentStatus,
)
from zheka.core.errors import (
    FLAT_NOT_FOUND,
    GROUP_NOT_FOUND,
    HOUSE_NOT_FOUND,
    REQUEST_NOT_FOUND,
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import (
    FlatId,
    HouseId,
    OrgId,
    RequestGroupId,
    RequestId,
    ResidentId,
    UserId,
)
from zheka.core.models import House, Request, RequestGroup, Resident, User
from zheka.core.services.category_executors import CategoryExecutorsService
from zheka.core.services.demo import demo_flat_number
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.request_groups import (
    GroupingService,
    complaint_sources,
    rules_of,
)
from zheka.core.services.request_status import check_transition, transition_path
from zheka.core.services.requests import (
    EMPTY_DESCRIPTION,
    RequestCardData,
    RequestRow,
    build_card,
    build_rows,
    stated,
)
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import (
    OPEN_STATUSES,
    RequestFilters,
    RequestsRepo,
)
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

EMPTY_REPLY = "Напишите ответ жителю"
GROUP_ALREADY_THERE = "Все заявки группы уже в этом статусе"
NO_CALLER_IDENTIFICATION = "Укажите квартиру или имя и телефон звонившего"
NOT_YOUR_REQUEST = "Эту заявку ведет другой исполнитель"
RESULT_PHOTO_REQUIRED = "Пришлите фото результата"
DECLINE_REASON_REQUIRED = "Напишите, почему не получится"
DECLINE_TOO_LATE = "От заявки отказываются до того, как работа сдана"
UNKNOWN_EXECUTOR = "Исполнитель"
RESIDENT_NOT_FOUND = "Житель не найден"
RESIDENT_BLOCKED = "Житель заблокирован в доме"
FLAT_NOT_RESIDENTS = "Квартира не совпадает с квартирой жителя"
NO_DEMO_REQUEST = "📝 Сначала подайте заявку по ссылке demo_resident_{number}"
_DEMO_OPEN = (RequestStatus.NEW, RequestStatus.ACCEPTED)


class AdminRequestRow(RequestRow):
    house: House
    author: User | None


class AdminRequestCardData(ZhekaType):
    card: RequestCardData
    author: User | None


class RequestGroupCardData(ZhekaType):
    group: RequestGroup
    house: House
    rows: list[AdminRequestRow]
    flats_count: int


class ExecutorView(ZhekaType):
    user: User
    active_requests: int


class PhoneRequestDraft(ZhekaType):
    house_id: HouseId
    category: RequestCategory
    description: str
    flat_id: FlatId | None = None
    caller_name: str | None = None
    caller_phone: str | None = None
    resident_id: ResidentId | None = None


class AdminRequestsService:
    __slots__ = (
        "_category_executors",
        "_events",
        "_grouping",
        "_houses",
        "_notifications",
        "_orgs",
        "_requests",
        "_residents",
        "_users",
    )

    def __init__(
        self,
        requests_repo: RequestsRepo,
        houses_repo: HousesRepo,
        users_repo: UsersRepo,
        orgs_repo: OrgsRepo,
        residents_repo: ResidentsRepo,
        grouping_service: GroupingService,
        notifications_service: NotificationsService,
        events_service: EventsService,
        category_executors_service: CategoryExecutorsService,
    ) -> None:
        self._requests = requests_repo
        self._houses = houses_repo
        self._users = users_repo
        self._orgs = orgs_repo
        self._residents = residents_repo
        self._grouping = grouping_service
        self._notifications = notifications_service
        self._events = events_service
        self._category_executors = category_executors_service

    async def inbox(
        self,
        org_id: OrgId,
        filters: RequestFilters,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminRequestRow], int]:
        requests, total = await self._requests.list_for_org(
            org_id,
            filters,
            datetime.now(UTC),
            limit,
            offset,
        )
        return await self._rows(requests), total

    async def card(self, org_id: OrgId, request_id: RequestId) -> AdminRequestCardData:
        request = await self._org_request(org_id, request_id)
        return await self._card(request)

    async def change_status(
        self,
        org_id: OrgId,
        request_id: RequestId,
        target: RequestStatus,
        comment: str | None,
        actor: UserId,
    ) -> AdminRequestCardData:
        request = await self._org_request(org_id, request_id)
        await self._move(request, target, comment, actor, RequestActorRole.STAFF)
        return await self._card(request)

    async def reply(
        self,
        org_id: OrgId,
        request_id: RequestId,
        text: str,
        actor: UserId,
    ) -> AdminRequestCardData:
        request = await self._org_request(org_id, request_id)
        reply = stated(text, EMPTY_REPLY)

        await self._requests.add_message(
            request.id,
            actor,
            RequestActorRole.STAFF.value,
            reply,
        )
        self._notifications.notify_author(
            request,
            texts.request_reply(request.id, request.category, reply),
        )
        return await self._card(request)

    async def assign(
        self,
        org_id: OrgId,
        request_id: RequestId,
        executor_user_id: UserId,
        actor: UserId,
    ) -> AdminRequestCardData:
        request = await self._org_request(org_id, request_id)
        await self._category_executors.check(org_id, executor_user_id)

        await self._requests.set_executor(request, executor_user_id)
        await self._events.record(
            EventType.REQUEST_ASSIGNED,
            user_id=actor,
            request_id=request_id,
            executor_user_id=executor_user_id,
        )
        self._notifications.open_executor_card(request_id)
        return await self._card(request)

    async def group_card(
        self,
        org_id: OrgId,
        group_id: RequestGroupId,
    ) -> RequestGroupCardData:
        group = await self._org_group(org_id, group_id)
        return await self._group_card(group)

    async def change_group_status(
        self,
        org_id: OrgId,
        group_id: RequestGroupId,
        target: RequestStatus,
        comment: str | None,
        actor: UserId,
    ) -> RequestGroupCardData:
        group = await self._org_group(org_id, group_id)
        members = await self._requests.list_for_group(group.id)
        paths = [(member, transition_path(member.status, target)) for member in members]
        if all(not path for _, path in paths):
            raise InvalidState(GROUP_ALREADY_THERE)

        for member, path in paths:
            for step in path:
                last = step is target
                await self._move(
                    member,
                    step,
                    comment if last else None,
                    actor,
                    RequestActorRole.STAFF,
                    notify_author=last,
                )
        if target is RequestStatus.DONE:
            await self._requests.set_group_status(group, RequestGroupStatus.CLOSED)
        return await self._group_card(group)

    async def create_phone(
        self,
        org_id: OrgId,
        draft: PhoneRequestDraft,
        actor: UserId,
    ) -> AdminRequestCardData:
        house = await self._houses.get_for_org(draft.house_id, org_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        description = stated(draft.description, EMPTY_DESCRIPTION)
        caller_name = (draft.caller_name or "").strip() or None
        caller_phone = (draft.caller_phone or "").strip() or None
        resident = await self._caller(draft)
        flat_id = draft.flat_id if resident is None else resident.flat_id
        if resident is None and flat_id is None and not (caller_name and caller_phone):
            raise InvalidRequest(NO_CALLER_IDENTIFICATION)

        if resident is None and flat_id is not None:
            flat = await self._houses.get_flat(flat_id)
            if flat is None or flat.house_id != draft.house_id:
                raise EntityNotFound(FLAT_NOT_FOUND)

        author = None if resident is None else resident.user_id
        request = await self._requests.create(
            house,
            flat_id,
            author,
            draft.category,
            description,
            RequestChannel.PHONE,
            None,
            None,
            is_staff_author=(
                author is None
                or await self._orgs.get_member(org_id, author) is not None
            ),
            caller_name=caller_name,
            caller_phone=caller_phone,
        )
        await self._requests.add_log(
            request.id,
            None,
            RequestStatus.NEW,
            actor,
            RequestActorRole.STAFF.value,
            datetime.now(UTC),
        )
        await self._grouping.attach(
            request,
            rules_of(await self._orgs.get_settings(org_id)),
            datetime.now(UTC),
        )
        await self._events.record(
            EventType.REQUEST_CREATED,
            user_id=actor,
            house_id=draft.house_id,
            category=draft.category.value,
            channel=RequestChannel.PHONE.value,
            has_photo=False,
            is_repeat=False,
        )
        await self._category_executors.assign_default(request, org_id)
        return await self._card(request)

    async def executors(self, org_id: OrgId) -> list[ExecutorView]:
        members = await self._orgs.list_members(org_id)
        executor_ids = [
            member.user_id for member in members if member.role is OrgRole.EXECUTOR
        ]
        users = await self._users.list_by_ids(executor_ids)
        active = await self._requests.count_active_by_executor(org_id)
        return [
            ExecutorView(user=user, active_requests=active.get(user.id, 0))
            for user in users
        ]

    async def _move(
        self,
        request: Request,
        target: RequestStatus,
        comment: str | None,
        actor: UserId,
        by_role: RequestActorRole,
        notify_author: bool = True,
    ) -> None:
        await self._requests.lock(request)
        current = request.status
        if target is current:
            return
        check_transition(
            current,
            target,
            by_role,
            has_author=request.author_user_id is not None,
        )
        at = datetime.now(UTC)
        await self._requests.set_status(request, target, at)
        await self._requests.add_log(
            request.id,
            current,
            target,
            actor,
            by_role.value,
            at,
        )
        note = None if comment is None else comment.strip()
        if note:
            await self._requests.add_message(request.id, actor, by_role.value, note)
        await self._events.record(
            EventType.REQUEST_STATUS_CHANGED,
            user_id=actor,
            request_id=request.id,
            **{"from": current.value, "to": target.value},
            by_role=by_role.value,
        )
        if not notify_author:
            return
        if target is RequestStatus.ON_REVIEW and request.author_user_id is not None:
            self._notifications.open_review_card(request.id)
        elif request.author_user_id is not None:
            house = await self._house(request.house_id)
            self._notifications.notify_author(
                request,
                texts.request_status_changed(request, house, note),
            )

    async def _card(self, request: Request) -> AdminRequestCardData:
        return AdminRequestCardData(
            card=await build_card(
                self._requests,
                self._houses,
                self._users,
                self._orgs,
                request,
                await self._house(request.house_id),
                with_internal=True,
            ),
            author=(
                None
                if request.author_user_id is None
                else await self._users.get_by_id(request.author_user_id)
            ),
        )

    async def _group_card(self, group: RequestGroup) -> RequestGroupCardData:
        members = await self._requests.list_for_group(group.id)
        rows = await self._rows(members)
        return RequestGroupCardData(
            group=group,
            house=await self._house(group.house_id),
            rows=rows,
            flats_count=len(complaint_sources(members)),
        )

    async def _rows(self, requests: Sequence[Request]) -> list[AdminRequestRow]:
        base_rows = await build_rows(
            self._requests,
            self._houses,
            self._users,
            requests,
        )
        houses = {
            house.id: house
            for house in await self._houses.list_by_ids(
                [request.house_id for request in requests],
            )
        }
        authors: dict[UserId | None, User] = {
            user.id: user
            for user in await self._users.list_by_ids(
                [
                    request.author_user_id
                    for request in requests
                    if request.author_user_id is not None
                ],
            )
        }
        return [
            AdminRequestRow(
                request=row.request,
                house=houses[row.request.house_id],
                flat=row.flat,
                author=authors.get(row.request.author_user_id),
                executor=row.executor,
                has_photos=row.has_photos,
                group_size=row.group_size,
            )
            for row in base_rows
        ]

    async def _org_request(self, org_id: OrgId, request_id: RequestId) -> Request:
        request = await self._requests.get_for_org(request_id, org_id)
        if request is None:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        return request

    async def _org_group(self, org_id: OrgId, group_id: RequestGroupId) -> RequestGroup:
        group = await self._requests.get_group_for_org(group_id, org_id)
        if group is None:
            raise EntityNotFound(GROUP_NOT_FOUND)
        return group

    async def _house(self, house_id: HouseId) -> House:
        house = await self._houses.get(house_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        return house

    async def executor_advance(
        self,
        user_id: UserId,
        request_id: RequestId,
        target: RequestStatus,
        photo_names: Sequence[str],
    ) -> None:
        request = await self._requests.get(request_id)
        if request is None:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        if not await self._can_act(request, user_id):
            raise NotEnoughRights(NOT_YOUR_REQUEST)
        check_transition(
            request.status,
            target,
            RequestActorRole.EXECUTOR,
            has_author=request.author_user_id is not None,
        )
        if target is RequestStatus.ON_REVIEW and not photo_names:
            photos = await self._requests.list_photos(request_id)
            if not any(photo.kind is RequestPhotoKind.RESULT for photo in photos):
                raise InvalidState(RESULT_PHOTO_REQUIRED)

        for name in photo_names:
            await self._requests.add_photo(
                request_id,
                name,
                RequestPhotoKind.RESULT,
                user_id,
            )
        await self._move(request, target, None, user_id, RequestActorRole.EXECUTOR)
        await self._events.record(
            EventType.EXECUTOR_STATUS_CHANGED,
            user_id=user_id,
            request_id=request_id,
            to=target.value,
        )

    async def executor_card(
        self,
        user_id: UserId,
        request_id: RequestId,
    ) -> RequestCardData | None:
        request = await self._requests.get(request_id)
        if request is None:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        if not await self._can_act(request, user_id):
            return None
        return (await self._card(request)).card

    async def _can_act(self, request: Request, user_id: UserId) -> bool:
        if request.executor_user_id != user_id:
            return False
        house = await self._house(request.house_id)
        if house.org_id is None:
            return False
        member = await self._orgs.get_member(house.org_id, user_id)
        return member is not None and member.role is OrgRole.EXECUTOR

    async def _caller(self, draft: PhoneRequestDraft) -> Resident | None:
        if draft.resident_id is None:
            return None
        resident = await self._residents.get(draft.resident_id)
        if resident is None or resident.house_id != draft.house_id:
            raise EntityNotFound(RESIDENT_NOT_FOUND)
        if resident.status is not ResidentStatus.ACTIVE:
            raise InvalidState(RESIDENT_BLOCKED)
        if draft.flat_id is not None and draft.flat_id != resident.flat_id:
            raise InvalidRequest(FLAT_NOT_RESIDENTS)
        return resident

    async def demo_request(
        self,
        org_id: OrgId,
        number: int,
        user_id: UserId,
    ) -> Request:
        request = None
        houses = await self._houses.list_for_org(org_id)
        if houses:
            flat = await self._houses.get_flat_by_number(
                houses[0].id,
                demo_flat_number(user_id),
            )
            if flat is not None:
                request = await self._requests.last_for_flat(flat.id, _DEMO_OPEN)
        if request is None:
            raise EntityNotFound(NO_DEMO_REQUEST.format(number=number))
        return request

    async def assign_demo(
        self,
        org_id: OrgId,
        request: Request,
        user_id: UserId,
    ) -> None:
        await self._move(
            request,
            RequestStatus.ACCEPTED,
            None,
            user_id,
            RequestActorRole.STAFF,
        )
        await self.assign(org_id, request.id, user_id, user_id)

    async def executor_decline(
        self,
        user_id: UserId,
        request_id: RequestId,
        reason: str,
    ) -> None:
        request = await self._requests.get(request_id)
        if request is None:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        await self._requests.lock(request)
        if not await self._can_act(request, user_id):
            raise NotEnoughRights(NOT_YOUR_REQUEST)
        if request.status not in OPEN_STATUSES:
            raise InvalidState(DECLINE_TOO_LATE)
        text = stated(reason, DECLINE_REASON_REQUIRED)

        await self._requests.set_executor(request, None)
        await self._requests.add_message(
            request_id,
            user_id,
            RequestActorRole.EXECUTOR.value,
            text,
            is_internal=True,
        )
        await self._events.record(
            EventType.EXECUTOR_DECLINED,
            user_id=user_id,
            request_id=request_id,
            status=request.status.value,
        )
        house = await self._house(request.house_id)
        executor = await self._users.get_by_id(user_id)
        members = (
            [] if house.org_id is None else await self._orgs.list_members(house.org_id)
        )
        self._notifications.notify_users(
            [member.user_id for member in members if member.role.is_staff],
            texts.executor_declined(
                request_id,
                request.category,
                UNKNOWN_EXECUTOR if executor is None else executor.name,
                text,
            ),
            category=NotificationCategory.REQUESTS,
            mandatory=False,
            app_button=texts.OPEN_REQUEST,
            app_path=admin_request_app_path(request_id),
        )
        self._notifications.open_executor_card(request_id, user_id)
