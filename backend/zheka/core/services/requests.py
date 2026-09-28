from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.deeplinks import admin_request_app_path, request_app_path
from zheka.core.enums import (
    EventType,
    NotificationCategory,
    OrgRole,
    RequestActorRole,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
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
from zheka.core.ids import FlatId, HouseId, RequestGroupId, RequestId, UserId
from zheka.core.models import (
    Flat,
    House,
    Organization,
    Request,
    RequestMessage,
    RequestPhoto,
    RequestStatusLog,
    Resident,
    User,
)
from zheka.core.services.category_executors import CategoryExecutorsService
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.houses import NOT_CONNECTED, is_connected
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.request_groups import (
    GroupingRules,
    GroupingService,
    SimilarRequests,
    rules_of,
)
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import OPEN_STATUSES, RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.yandex import YandexClassifier

MAX_PHOTOS = 12
AUTO_CLOSE_AFTER = timedelta(hours=48)
MIN_RATING = 1
MAX_RATING = 5

BLOCKED = "Вы заблокированы в этом доме"
GROUP_CLOSED = "Группа заявок уже закрыта"
GROUP_OTHER_CATEGORY = "Группа заявок собрана по другой категории"
EMPTY_DESCRIPTION = "Опишите проблему"
TOO_MANY_PHOTOS = f"К заявке можно приложить не больше {MAX_PHOTOS} фото"
RATE_NOT_DONE = "Оценку ставят принятой жителем заявке"
RATED_ALREADY = "Оценка уже поставлена"
REPEAT_NOT_DONE = "Повторную заявку подают после приемки или по выполненной"
REJECTION_COMMENT_REQUIRED = "Расскажите, что сделано плохо"
ACCEPT_NOT_ON_REVIEW = "Работу принимают на приемке"
REJECT_NOT_ON_REVIEW = "Работу возвращают только с приемки"
RATING_OUT_OF_RANGE = f"Оценка - от {MIN_RATING} до {MAX_RATING}"
ESCALATED_ALREADY = "Руководство УК уже уведомлено"
ESCALATE_NOT_OVERDUE = "Руководство зовут, только когда срок открытой заявки истек"


class RequestDraft(ZhekaType):
    category: RequestCategory
    description: str
    flat_id: FlatId | None = None
    photos: Sequence[str] = ()
    group_id: RequestGroupId | None = None
    llm_suggested: bool = False
    llm_accepted: bool = False


class RequestMessageView(ZhekaType):
    message: RequestMessage
    author: User | None


class RequestRow(ZhekaType):
    request: Request
    flat: Flat | None
    has_photos: bool
    group_size: int
    executor: User | None


class RequestCardData(ZhekaType):
    request: Request
    house: House
    org: Organization | None
    flat: Flat | None
    issue_photos: Sequence[RequestPhoto]
    result_photos: Sequence[RequestPhoto]
    timeline: Sequence[RequestStatusLog]
    messages: Sequence[RequestMessageView]
    group_size: int
    executor: User | None
    can_review: bool
    can_rate: bool
    auto_close_at: datetime | None
    can_demo_expire: bool


class RequestsService:
    __slots__ = (
        "_category_executors",
        "_classifier",
        "_events",
        "_files",
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
        residents_repo: ResidentsRepo,
        users_repo: UsersRepo,
        orgs_repo: OrgsRepo,
        files_service: FilesService,
        grouping_service: GroupingService,
        notifications_service: NotificationsService,
        events_service: EventsService,
        classifier: YandexClassifier,
        category_executors_service: CategoryExecutorsService,
    ) -> None:
        self._requests = requests_repo
        self._houses = houses_repo
        self._residents = residents_repo
        self._users = users_repo
        self._orgs = orgs_repo
        self._files = files_service
        self._grouping = grouping_service
        self._notifications = notifications_service
        self._events = events_service
        self._classifier = classifier
        self._category_executors = category_executors_service

    async def create(
        self,
        user_id: UserId,
        house_id: HouseId,
        draft: RequestDraft,
        channel: RequestChannel = RequestChannel.MINIAPP,
    ) -> RequestCardData:
        resident = await self._active_resident(user_id, house_id)
        house = await self._get_house(house_id)
        org = None if house.org_id is None else await self._orgs.get(house.org_id)
        if not is_connected(house, org):
            raise InvalidState(NOT_CONNECTED)
        description = stated(draft.description, EMPTY_DESCRIPTION)
        if draft.flat_id is not None and resident.flat_id != draft.flat_id:
            raise EntityNotFound(FLAT_NOT_FOUND)
        photos = self._checked_photos(draft.photos)
        group_id = await self._checked_group(draft.group_id, house_id, draft.category)

        request = await self._requests.create(
            house,
            draft.flat_id,
            user_id,
            draft.category,
            description,
            channel,
            group_id,
            None,
            is_staff_author=await self._is_staff(house, user_id),
        )
        await self._add_photos(request, photos, user_id)
        await self._open(request, user_id)
        await self._group(request, house, group_id)
        await self._events.record(
            EventType.REQUEST_CREATED,
            user_id=user_id,
            house_id=house_id,
            category=draft.category.value,
            channel=channel.value,
            has_photo=bool(photos),
            is_repeat=False,
            llm_suggested=draft.llm_suggested,
            llm_accepted=draft.llm_accepted,
        )
        if draft.llm_suggested and draft.llm_accepted:
            await self._events.record(
                EventType.LLM_ACCEPTED,
                user_id=user_id,
                house_id=house_id,
                category=draft.category.value,
            )
        await self._category_executors.assign_default(request, house.org_id)
        await self._notify_staff(request, house, texts.request_created(request, house))
        return await self._built_card(request, house)

    async def repeat(
        self,
        user_id: UserId,
        request_id: RequestId,
        description: str | None,
        photos: Sequence[str],
        channel: RequestChannel = RequestChannel.MINIAPP,
    ) -> RequestCardData:
        parent = await self._own_request(user_id, request_id)
        await self._requests.lock(parent)
        rejected_on_review = parent.status is RequestStatus.ON_REVIEW
        if not rejected_on_review and parent.status is not RequestStatus.DONE:
            raise InvalidState(REPEAT_NOT_DONE)

        house_id = parent.house_id
        await self._active_resident(user_id, house_id)
        house = await self._get_house(house_id)
        if rejected_on_review:
            text = stated(description or "", REJECTION_COMMENT_REQUIRED)
        else:
            text = stated(
                parent.description if description is None else description,
                EMPTY_DESCRIPTION,
            )
        checked = self._checked_photos(photos)
        if rejected_on_review:
            await self._complete_review(
                parent,
                user_id,
                RequestCompletionReason.RESIDENT_REJECTED,
                datetime.now(UTC),
            )

        request = await self._requests.create(
            house,
            parent.flat_id,
            user_id,
            parent.category,
            text,
            channel,
            None,
            parent.id,
            is_staff_author=await self._is_staff(house, user_id),
        )
        await self._add_photos(request, checked, user_id)
        await self._open(request, user_id)
        await self._events.record(
            EventType.REQUEST_CREATED,
            user_id=user_id,
            house_id=house_id,
            category=parent.category.value,
            channel=channel.value,
            has_photo=bool(checked),
            is_repeat=True,
            parent_request_id=parent.id,
        )
        await self._category_executors.assign_default(request, house.org_id)
        await self._notify_staff(request, house, texts.request_created(request, house))
        return await self._built_card(request, house)

    async def rate(
        self,
        user_id: UserId,
        request_id: RequestId,
        rating: int,
        feedback: str | None,
    ) -> RequestCardData:
        if not MIN_RATING <= rating <= MAX_RATING:
            raise InvalidRequest(RATING_OUT_OF_RANGE)
        request = await self._own_request(user_id, request_id)
        await self._active_resident(user_id, request.house_id)

        if request.completion_reason is not RequestCompletionReason.RESIDENT_ACCEPTED:
            raise InvalidState(RATE_NOT_DONE)
        if request.rating is not None:
            raise InvalidState(RATED_ALREADY)

        feedback = (feedback or "").strip() or None
        await self._requests.set_rating(request, rating, feedback)
        await self._events.record(
            EventType.REQUEST_RATED,
            user_id=user_id,
            request_id=request_id,
            score=rating,
            has_comment=request.feedback is not None,
        )
        return await self.get_card(user_id, request_id)

    async def accept(self, user_id: UserId, request_id: RequestId) -> RequestCardData:
        request = await self._own_request(user_id, request_id)
        await self._active_resident(user_id, request.house_id)
        await self._requests.lock(request)
        if request.status is not RequestStatus.ON_REVIEW:
            raise InvalidState(ACCEPT_NOT_ON_REVIEW)

        await self._complete_review(
            request,
            user_id,
            RequestCompletionReason.RESIDENT_ACCEPTED,
            datetime.now(UTC),
        )
        return await self.get_card(user_id, request_id)

    async def auto_close(self, now: datetime) -> int:
        requests = await self._requests.list_reviewed_before(now - AUTO_CLOSE_AFTER)
        for request in requests:
            await self._complete_review(
                request,
                None,
                RequestCompletionReason.AUTO_CLOSED,
                now,
            )
            self._notifications.notify_author(
                request,
                texts.request_auto_closed(request.id),
            )
        return len(requests)

    async def _complete_review(
        self,
        request: Request,
        user_id: UserId | None,
        completion_reason: RequestCompletionReason,
        at: datetime,
    ) -> None:
        auto = completion_reason is RequestCompletionReason.AUTO_CLOSED
        by_role = RequestActorRole.SYSTEM if auto else RequestActorRole.RESIDENT
        await self._requests.set_status(
            request,
            RequestStatus.DONE,
            at,
            completion_reason=completion_reason,
        )
        await self._requests.add_log(
            request.id,
            RequestStatus.ON_REVIEW,
            RequestStatus.DONE,
            user_id,
            by_role.value,
            at,
        )
        await self._events.record(
            EventType.REQUEST_STATUS_CHANGED,
            user_id=user_id,
            request_id=request.id,
            **{"from": RequestStatus.ON_REVIEW.value, "to": RequestStatus.DONE.value},
            by_role=by_role.value,
        )
        if auto:
            await self._events.record(
                EventType.REQUEST_AUTO_CLOSED,
                request_id=request.id,
            )
            return
        await self._events.record(
            EventType.REQUEST_REVIEWED,
            user_id=user_id,
            request_id=request.id,
            accepted=completion_reason is RequestCompletionReason.RESIDENT_ACCEPTED,
        )

    async def get_card(self, user_id: UserId, request_id: RequestId) -> RequestCardData:
        request = await self._own_request(user_id, request_id)
        house = await self._get_house(request.house_id)
        return await self._built_card(request, house)

    async def list_mine(
        self,
        user_id: UserId,
        house_id: HouseId,
        status: RequestStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[RequestRow], int]:
        requests, total = await self._requests.list_for_user(
            user_id,
            house_id,
            status,
            limit,
            offset,
        )
        rows = await build_rows(self._requests, self._houses, self._users, requests)
        return rows, total

    async def similar(
        self,
        user_id: UserId,
        house_id: HouseId,
        category: RequestCategory,
    ) -> SimilarRequests:
        resident = await self._active_resident(user_id, house_id)
        return await self._grouping.similar(
            house_id,
            category,
            await self._rules(await self._get_house(house_id)),
            datetime.now(UTC),
            resident.flat_id,
            user_id,
        )

    async def _group(
        self,
        request: Request,
        house: House,
        joined_group_id: RequestGroupId | None,
    ) -> None:
        if joined_group_id is not None:
            await self._grouping.joined(request, joined_group_id)
            return
        await self._grouping.attach(
            request,
            await self._rules(house),
            datetime.now(UTC),
        )

    async def _rules(self, house: House) -> GroupingRules:
        org_id = house.org_id
        return rules_of(
            None if org_id is None else await self._orgs.get_settings(org_id),
        )

    async def _built_card(self, request: Request, house: House) -> RequestCardData:
        return await build_card(
            self._requests,
            self._houses,
            self._users,
            self._orgs,
            request,
            house,
            authored=True,
        )

    async def _open(self, request: Request, user_id: UserId) -> None:
        await self._requests.add_log(
            request.id,
            None,
            RequestStatus.NEW,
            user_id,
            RequestActorRole.RESIDENT.value,
            datetime.now(UTC),
        )

    async def _add_photos(
        self,
        request: Request,
        photos: Sequence[str],
        user_id: UserId,
    ) -> None:
        for name in photos:
            await self._requests.add_photo(
                request.id,
                name,
                RequestPhotoKind.ISSUE,
                user_id,
            )

    def _checked_photos(self, photos: Sequence[str]) -> Sequence[str]:
        if len(photos) > MAX_PHOTOS:
            raise InvalidRequest(TOO_MANY_PHOTOS)
        for name in photos:
            self._files.path_of(name)
        return photos

    async def _active_resident(self, user_id: UserId, house_id: HouseId) -> Resident:
        resident = await self._residents.get_for_house(user_id, house_id)
        if resident is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        if resident.status is ResidentStatus.BLOCKED:
            raise NotEnoughRights(BLOCKED)
        return resident

    async def _own_request(self, user_id: UserId, request_id: RequestId) -> Request:
        request = await self._requests.get(request_id)
        if request is None or request.author_user_id != user_id:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        return request

    async def _checked_group(
        self,
        group_id: RequestGroupId | None,
        house_id: HouseId,
        category: RequestCategory,
    ) -> RequestGroupId | None:
        if group_id is None:
            return None
        group = await self._requests.get_group(group_id)
        if group is None or group.house_id != house_id:
            raise EntityNotFound(GROUP_NOT_FOUND)
        if group.category is not category:
            raise InvalidRequest(GROUP_OTHER_CATEGORY)
        if group.status is not RequestGroupStatus.OPEN:
            raise InvalidState(GROUP_CLOSED)
        return group_id

    async def _is_staff(self, house: House, user_id: UserId) -> bool:
        if house.org_id is None:
            return False
        member = await self._orgs.get_member(house.org_id, user_id)
        return member is not None

    async def _get_house(self, house_id: HouseId) -> House:
        house = await self._houses.get(house_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        return house

    async def reject(
        self,
        user_id: UserId,
        request_id: RequestId,
        comment: str,
        channel: RequestChannel,
    ) -> RequestCardData:
        parent = await self._own_request(user_id, request_id)
        if parent.status is not RequestStatus.ON_REVIEW:
            raise InvalidState(REJECT_NOT_ON_REVIEW)
        return await self.repeat(user_id, request_id, comment, [], channel)

    async def export(self, user_id: UserId, request_id: RequestId) -> RequestCardData:
        card = await self.get_card(user_id, request_id)
        await self._events.record(
            EventType.REQUEST_EXPORTED,
            user_id=user_id,
            request_id=request_id,
        )
        return card

    async def classify(self, user_id: UserId, text: str) -> RequestCategory | None:
        category = await self._classifier.classify(text)
        if category is not None:
            await self._events.record(
                EventType.LLM_SUGGESTED,
                user_id=user_id,
                category=category.value,
            )
        return category

    async def _notify_staff(self, request: Request, house: House, text: str) -> None:
        if house.org_id is None:
            return
        members = await self._orgs.list_members(house.org_id)
        self._notifications.notify_users(
            [
                member.user_id
                for member in members
                if member.role.is_staff and member.user_id != request.author_user_id
            ],
            text,
            category=NotificationCategory.REQUESTS,
            mandatory=False,
            app_button=texts.OPEN_REQUEST,
            app_path=admin_request_app_path(request.id),
        )

    async def watch_deadlines(self, now: datetime) -> int:
        requests = await self._requests.list_deadline_due(now)
        for request in requests:
            await self._watch(request, await self._get_house(request.house_id), now)
        return len(requests)

    async def demo_expire(
        self,
        user_id: UserId,
        request_id: RequestId,
        now: datetime,
    ) -> RequestCardData:
        request = await self._own_request(user_id, request_id)
        await self._requests.lock(request)
        house = await self._get_house(request.house_id)
        org = None if house.org_id is None else await self._orgs.get(house.org_id)
        if not demo_expirable(request, org, now):
            raise EntityNotFound(REQUEST_NOT_FOUND)
        await self._requests.set_deadline(request, now - timedelta(minutes=1))
        await self._watch(request, house, now)
        return await self._built_card(request, house)

    async def _watch(self, request: Request, house: House, now: datetime) -> None:
        overdue = request.deadline_at <= now
        await self._requests.mark_deadline(request, now, overdue=overdue)
        if not overdue:
            await self._notify_crew(
                request,
                house,
                texts.deadline_warning(request, house, now),
            )
            return
        await self._notify_crew(
            request,
            house,
            texts.request_overdue_staff(request, house),
        )
        if request.author_user_id is not None:
            self._notifications.notify_user(
                request.author_user_id,
                texts.request_overdue_author(request),
                category=NotificationCategory.REQUESTS,
                mandatory=True,
                app_button=texts.COMPLAINT_BUTTON,
                app_path=request_app_path(request.id),
            )
        chairman = await self._residents.get_chairman(house.id)
        if (
            chairman is not None
            and chairman.status is not ResidentStatus.BLOCKED
            and chairman.user_id != request.author_user_id
        ):
            self._notifications.notify_user(
                chairman.user_id,
                texts.request_overdue_chairman(request),
                category=NotificationCategory.REQUESTS,
                mandatory=False,
            )

    async def _notify_crew(self, request: Request, house: House, text: str) -> None:
        await self._notify_staff(request, house, text)
        executor_id = request.executor_user_id
        if (
            house.org_id is None
            or executor_id is None
            or executor_id == request.author_user_id
        ):
            return
        member = await self._orgs.get_member(house.org_id, executor_id)
        if member is not None and member.role is OrgRole.EXECUTOR:
            self._notifications.notify_user(
                executor_id,
                text,
                category=NotificationCategory.REQUESTS,
                mandatory=False,
            )

    async def escalate(
        self,
        user_id: UserId,
        request_id: RequestId,
        now: datetime,
    ) -> RequestCardData:
        request = await self._own_request(user_id, request_id)
        await self._active_resident(user_id, request.house_id)
        await self._requests.lock(request)
        if request.escalated_at is not None:
            raise InvalidState(ESCALATED_ALREADY)
        if request.status not in OPEN_STATUSES or request.deadline_at > now:
            raise InvalidState(ESCALATE_NOT_OVERDUE)
        house = await self._get_house(request.house_id)
        await self._requests.escalate(request, now)
        await self._events.record(
            EventType.REQUEST_ESCALATED,
            user_id=user_id,
            request_id=request.id,
            house_id=house.id,
            category=request.category.value,
        )
        self._notifications.notify_user(
            user_id,
            texts.request_escalated_author(request),
            category=NotificationCategory.REQUESTS,
            mandatory=False,
            app_button=texts.OPEN_REQUEST,
            app_path=request_app_path(request.id),
        )
        await self._notify_crew(
            request,
            house,
            texts.request_escalated(request, house, now),
        )
        return await self._built_card(request, house)


async def build_rows(
    requests_repo: RequestsRepo,
    houses_repo: HousesRepo,
    users_repo: UsersRepo,
    requests: Sequence[Request],
) -> list[RequestRow]:
    photo_counts = await requests_repo.count_photos(
        [request.id for request in requests],
    )
    group_sizes = await requests_repo.count_by_group(
        {request.group_id for request in requests if request.group_id is not None},
    )
    flats: dict[FlatId | None, Flat] = {
        flat.id: flat
        for flat in await houses_repo.list_flats_by_ids(
            [request.flat_id for request in requests if request.flat_id is not None],
        )
    }
    executors: dict[UserId | None, User] = {
        user.id: user
        for user in await users_repo.list_by_ids(
            [
                request.executor_user_id
                for request in requests
                if request.executor_user_id is not None
            ],
        )
    }
    return [
        RequestRow(
            request=request,
            flat=flats.get(request.flat_id),
            has_photos=photo_counts.get(request.id, 0) > 0,
            group_size=(
                0 if request.group_id is None else group_sizes.get(request.group_id, 0)
            ),
            executor=executors.get(request.executor_user_id),
        )
        for request in requests
    ]


async def build_card(
    requests_repo: RequestsRepo,
    houses_repo: HousesRepo,
    users_repo: UsersRepo,
    orgs_repo: OrgsRepo,
    request: Request,
    house: House,
    *,
    authored: bool = False,
    with_internal: bool = False,
) -> RequestCardData:
    photos = await requests_repo.list_photos(request.id)
    messages = [
        message
        for message in await requests_repo.list_messages(request.id)
        if with_internal or not message.is_internal
    ]
    authors = {
        user.id: user
        for user in await users_repo.list_by_ids(
            [message.author_user_id for message in messages],
        )
    }
    group_sizes = await requests_repo.count_by_group(
        [] if request.group_id is None else [request.group_id],
    )
    executor = (
        None
        if request.executor_user_id is None
        else await users_repo.get_by_id(request.executor_user_id)
    )
    org = None if house.org_id is None else await orgs_repo.get(house.org_id)
    return RequestCardData(
        request=request,
        house=house,
        org=org,
        flat=(
            None
            if request.flat_id is None
            else await houses_repo.get_flat(request.flat_id)
        ),
        issue_photos=[
            photo for photo in photos if photo.kind is RequestPhotoKind.ISSUE
        ],
        result_photos=[
            photo for photo in photos if photo.kind is RequestPhotoKind.RESULT
        ],
        timeline=await requests_repo.list_log(request.id),
        messages=[
            RequestMessageView(
                message=message,
                author=authors.get(message.author_user_id),
            )
            for message in messages
        ],
        group_size=sum(group_sizes.values()),
        executor=executor,
        can_review=request.status is RequestStatus.ON_REVIEW,
        can_rate=(
            request.completion_reason is RequestCompletionReason.RESIDENT_ACCEPTED
            and request.rating is None
        ),
        auto_close_at=(
            request.reviewed_at + AUTO_CLOSE_AFTER
            if request.status is RequestStatus.ON_REVIEW
            and request.reviewed_at is not None
            else None
        ),
        can_demo_expire=authored and demo_expirable(request, org, datetime.now(UTC)),
    )


def stated(text: str, refusal: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise InvalidRequest(refusal)
    return stripped


def demo_expirable(
    request: Request,
    org: Organization | None,
    now: datetime,
) -> bool:
    return (
        org is not None
        and org.is_demo
        and request.status in OPEN_STATUSES
        and request.deadline_at > now
    )
