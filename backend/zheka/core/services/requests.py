from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import (
    EventType,
    NotificationCategory,
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
    UserId,
)
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
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.request_groups import (
    GroupingRules,
    GroupingService,
    SimilarRequests,
    rules_of,
)
from zheka.core.services.request_status import check_transition
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.yandex import YandexClassifier

# потолок вложений в одном сообщении MAX, он же потолок фото у заявки
MAX_PHOTOS = 12
# заявку, оставленную на приемке, закрывает auto_close_reviewed_requests; тот же
# срок карточка показывает как дедлайн автозакрытия, пока заявка ON_REVIEW
AUTO_CLOSE_AFTER = timedelta(hours=48)
# оценку ставят и мини-апп, и бот; кнопка бота присылает любую строку, поэтому
# границы проверяет сервис, а схема берет их отсюда
MIN_RATING = 1
MAX_RATING = 5

BLOCKED = "Вы заблокированы в этом доме"
NOT_A_RESIDENT = "Дом не найден"
REQUEST_NOT_FOUND = "Заявка не найдена"
FLAT_NOT_FOUND = "Квартира не найдена"
GROUP_NOT_FOUND = "Группа заявок не найдена"
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
# from - ключевое слово питона, поэтому пара едет в record распаковкой
_CLOSED_FROM_REVIEW: dict[str, Any] = {
    "from": RequestStatus.ON_REVIEW.value,
    "to": RequestStatus.DONE.value,
}


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


class RequestsService:
    __slots__ = (
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

    async def create(
        self,
        user_id: UserId,
        house_id: HouseId,
        draft: RequestDraft,
        channel: RequestChannel = RequestChannel.MINIAPP,
    ) -> RequestCardData:
        resident = await self._active_resident(user_id, house_id)
        house = await self._get_house(house_id)
        description = _stated(draft.description)
        flat = await self._author_flat(resident, draft.flat_id)
        photos = self._checked_photos(draft.photos)
        group_id = await self._checked_group(draft.group_id, house_id, draft.category)

        request = await self._requests.create(
            house_id,
            None if flat is None else FlatId(flat.id),
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
        # принять можно только то, что было подсказано; флаги присылает клиент
        if draft.llm_suggested and draft.llm_accepted:
            await self._events.record(
                EventType.LLM_ACCEPTED,
                user_id=user_id,
                house_id=house_id,
                category=draft.category.value,
            )
        return await self._built_card(request, house, flat)

    async def repeat(
        self,
        user_id: UserId,
        request_id: RequestId,
        description: str | None,
        photos: Sequence[str],
        channel: RequestChannel = RequestChannel.MINIAPP,
    ) -> RequestCardData:
        parent = await self._own_request(user_id, request_id)
        rejected_on_review = parent.status is RequestStatus.ON_REVIEW
        if not rejected_on_review and parent.status is not RequestStatus.DONE:
            raise InvalidState(REPEAT_NOT_DONE)

        house_id = HouseId(parent.house_id)
        await self._active_resident(user_id, house_id)
        house = await self._get_house(house_id)
        # описание и фото у повтора свои, остальное - копия родителя: житель
        # жалуется на ту же проблему в той же квартире
        if rejected_on_review:
            # отказ от результата должен объяснить исполнителю, почему работа
            # вернулась: это описание становится первым текстом повтора
            comment = "" if description is None else description.strip()
            if not comment:
                raise InvalidRequest(REJECTION_COMMENT_REQUIRED)
            text = comment
        else:
            text = _stated(parent.description if description is None else description)
        checked = self._checked_photos(photos)
        flat = (
            None
            if parent.flat_id is None
            else await self._houses.get_flat(FlatId(parent.flat_id))
        )
        if rejected_on_review:
            await self._complete_review(
                parent,
                user_id,
                RequestCompletionReason.RESIDENT_REJECTED,
            )

        request = await self._requests.create(
            house_id,
            None if parent.flat_id is None else FlatId(parent.flat_id),
            user_id,
            parent.category,
            text,
            channel,
            None,
            RequestId(parent.id),
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
            parent_request_id=RequestId(parent.id),
        )
        return await self._built_card(request, house, flat)

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
        await self._active_resident(user_id, HouseId(request.house_id))

        if request.completion_reason is not RequestCompletionReason.RESIDENT_ACCEPTED:
            raise InvalidState(RATE_NOT_DONE)
        if request.rating is not None:
            raise InvalidState(RATED_ALREADY)

        await self._requests.set_rating(request, rating, _stated_or_none(feedback))
        await self._events.record(
            EventType.REQUEST_RATED,
            user_id=user_id,
            request_id=request_id,
            score=rating,
            has_comment=request.feedback is not None,
        )
        return await self.get_card(user_id, request_id)

    async def accept(
        self,
        user_id: UserId,
        request_id: RequestId,
    ) -> RequestCardData:
        request = await self._own_request(user_id, request_id)
        await self._active_resident(user_id, HouseId(request.house_id))
        if request.status is not RequestStatus.ON_REVIEW:
            raise InvalidState(ACCEPT_NOT_ON_REVIEW)

        await self._complete_review(
            request,
            user_id,
            RequestCompletionReason.RESIDENT_ACCEPTED,
        )
        return await self.get_card(user_id, request_id)

    async def auto_close(self, now: datetime) -> int:
        requests = await self._requests.list_reviewed_before(
            now - AUTO_CLOSE_AFTER,
        )
        for request in requests:
            check_transition(
                request.status,
                RequestStatus.DONE,
                RequestActorRole.SYSTEM,
                has_author=request.author_user_id is not None,
            )
            await self._requests.set_status(
                request,
                RequestStatus.DONE,
                now,
                completion_reason=RequestCompletionReason.AUTO_CLOSED,
            )
            await self._requests.add_log(
                RequestId(request.id),
                RequestStatus.ON_REVIEW,
                RequestStatus.DONE,
                None,
                RequestActorRole.SYSTEM.value,
                now,
            )
            await self._events.record(
                EventType.REQUEST_STATUS_CHANGED,
                request_id=RequestId(request.id),
                **_CLOSED_FROM_REVIEW,
                by_role=RequestActorRole.SYSTEM.value,
            )
            await self._events.record(
                EventType.REQUEST_AUTO_CLOSED,
                request_id=RequestId(request.id),
            )
            if request.author_user_id is not None:
                self._notifications.notify_user(
                    UserId(request.author_user_id),
                    texts.request_auto_closed(RequestId(request.id)),
                    category=NotificationCategory.REQUESTS,
                    mandatory=True,
                )
        return len(requests)

    async def _complete_review(
        self,
        request: Request,
        user_id: UserId,
        completion_reason: RequestCompletionReason,
    ) -> None:
        check_transition(
            request.status,
            RequestStatus.DONE,
            RequestActorRole.RESIDENT,
            has_author=True,
        )

        at = datetime.now(UTC)
        await self._requests.set_status(
            request,
            RequestStatus.DONE,
            at,
            completion_reason=completion_reason,
        )
        await self._requests.add_log(
            RequestId(request.id),
            RequestStatus.ON_REVIEW,
            RequestStatus.DONE,
            user_id,
            RequestActorRole.RESIDENT.value,
            at,
        )
        await self._events.record(
            EventType.REQUEST_STATUS_CHANGED,
            user_id=user_id,
            request_id=RequestId(request.id),
            **_CLOSED_FROM_REVIEW,
            by_role=RequestActorRole.RESIDENT.value,
        )
        await self._events.record(
            EventType.REQUEST_REVIEWED,
            user_id=user_id,
            request_id=RequestId(request.id),
            accepted=completion_reason is RequestCompletionReason.RESIDENT_ACCEPTED,
        )

    async def get_card(self, user_id: UserId, request_id: RequestId) -> RequestCardData:
        request = await self._own_request(user_id, request_id)
        house = await self._get_house(HouseId(request.house_id))
        flat = (
            None
            if request.flat_id is None
            else await self._houses.get_flat(FlatId(request.flat_id))
        )
        return await self._built_card(request, house, flat)

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
            None if resident.flat_id is None else FlatId(resident.flat_id),
            user_id,
        )

    async def _group(
        self,
        request: Request,
        house: House,
        joined_group_id: RequestGroupId | None,
    ) -> None:
        # житель, нажавший «присоединиться», уже в группе - искать нечего
        if joined_group_id is not None:
            await self._grouping.joined(request, joined_group_id)
            return
        await self._grouping.attach(
            request,
            await self._rules(house),
            datetime.now(UTC),
        )

    async def _rules(self, house: House) -> GroupingRules:
        if house.org_id is None:
            return rules_of(None)
        return rules_of(await self._orgs.get_settings(OrgId(house.org_id)))

    async def _built_card(
        self,
        request: Request,
        house: House,
        flat: Flat | None,
    ) -> RequestCardData:
        return await build_card(
            self._requests,
            self._users,
            self._orgs,
            request,
            house,
            flat,
        )

    async def _open(self, request: Request, user_id: UserId) -> None:
        # статус NEW - такая же запись в журнале, как и любая следующая:
        # ни один путь не меняет requests.status без строки в логе
        await self._requests.add_log(
            RequestId(request.id),
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
                RequestId(request.id),
                name,
                RequestPhotoKind.ISSUE,
                user_id,
            )

    def _checked_photos(self, photos: Sequence[str]) -> Sequence[str]:
        if len(photos) > MAX_PHOTOS:
            raise InvalidRequest(TOO_MANY_PHOTOS)
        # имя из upload_file, а не произвольная строка: подделка иначе дожила
        # бы до карточки и уронила бы ее целиком на подписи ссылки
        for name in photos:
            self._files.path_of(name)
        return photos

    async def _active_resident(self, user_id: UserId, house_id: HouseId) -> Resident:
        resident = await self._residents.get_for_house(user_id, house_id)
        # чужой дом отвечает 404, а не 403: 403 подтвердил бы, что дом есть
        if resident is None:
            raise EntityNotFound(NOT_A_RESIDENT)
        if resident.status is ResidentStatus.BLOCKED:
            raise NotEnoughRights(BLOCKED)
        return resident

    async def _own_request(self, user_id: UserId, request_id: RequestId) -> Request:
        request = await self._requests.get(request_id)
        # чужая заявка неотличима от несуществующей
        if request is None or request.author_user_id != user_id:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        return request

    async def _author_flat(
        self,
        resident: Resident,
        flat_id: FlatId | None,
    ) -> Flat | None:
        # заявку про свою квартиру житель подает по своей квартире, про общее
        # имущество - без квартиры вовсе. Чужой номер тут не нужен никому
        if flat_id is None:
            return None
        if resident.flat_id != flat_id:
            raise EntityNotFound(FLAT_NOT_FOUND)
        return await self._houses.get_flat(flat_id)

    async def _checked_group(
        self,
        group_id: RequestGroupId | None,
        house_id: HouseId,
        category: RequestCategory,
    ) -> RequestGroupId | None:
        # склейку собирает блок 9, здесь только присоединение к готовой группе
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
        member = await self._orgs.get_member(OrgId(house.org_id), user_id)
        return member is not None

    async def _get_house(self, house_id: HouseId) -> House:
        house = await self._houses.get(house_id)
        if house is None:
            raise EntityNotFound("Дом не найден")
        return house

    async def reject(
        self,
        user_id: UserId,
        request_id: RequestId,
        comment: str,
        channel: RequestChannel,
    ) -> RequestCardData:
        # repeat принимает и выполненную заявку - это повтор мини-аппа. Отказ
        # бота только с приемки: иначе забытое окно ввода превратило бы любое
        # следующее сообщение жителя в повторную заявку по закрытой
        parent = await self._own_request(user_id, request_id)
        if parent.status is not RequestStatus.ON_REVIEW:
            raise InvalidState(REJECT_NOT_ON_REVIEW)
        return await self.repeat(user_id, request_id, comment, [], channel)

    async def export(self, user_id: UserId, request_id: RequestId) -> RequestCardData:
        card = await self.get_card(user_id, request_id)
        # каждое открытие печатной страницы - отдельная выгрузка
        await self._events.record(
            EventType.REQUEST_EXPORTED,
            user_id=user_id,
            request_id=request_id,
        )
        return card

    async def classify(self, user_id: UserId, text: str) -> RequestCategory | None:
        # ponytail: каждый вызов - платный запрос, и сдерживает их только
        # debounce фронта; лимит на пользователя - когда об этом скажет счет
        category = await self._classifier.classify(text)
        if category is not None:
            await self._events.record(
                EventType.LLM_SUGGESTED,
                user_id=user_id,
                category=category.value,
            )
        return category


async def build_rows(
    requests_repo: RequestsRepo,
    houses_repo: HousesRepo,
    users_repo: UsersRepo,
    requests: Sequence[Request],
) -> list[RequestRow]:
    # общий для кабинета жителя (list_mine) и кабинета УК (inbox) шаг:
    # посчитать фото и размер группы и подтянуть квартиры с исполнителями
    # одним запросом на весь список, а не по одному на заявку
    photo_counts = await requests_repo.count_photos(
        [RequestId(request.id) for request in requests],
    )
    group_sizes = await requests_repo.count_by_group(
        {
            RequestGroupId(request.group_id)
            for request in requests
            if request.group_id is not None
        },
    )
    flats = {
        FlatId(flat.id): flat
        for flat in await houses_repo.list_flats_by_ids(
            [
                FlatId(request.flat_id)
                for request in requests
                if request.flat_id is not None
            ],
        )
    }
    executors = {
        UserId(user.id): user
        for user in await users_repo.list_by_ids(
            [
                UserId(request.executor_user_id)
                for request in requests
                if request.executor_user_id is not None
            ],
        )
    }
    return [
        RequestRow(
            request=request,
            flat=None if request.flat_id is None else flats.get(request.flat_id),
            has_photos=photo_counts.get(RequestId(request.id), 0) > 0,
            group_size=(
                0
                if request.group_id is None
                else group_sizes.get(RequestGroupId(request.group_id), 0)
            ),
            executor=(
                None
                if request.executor_user_id is None
                else executors.get(request.executor_user_id)
            ),
        )
        for request in requests
    ]


async def build_card(
    requests_repo: RequestsRepo,
    users_repo: UsersRepo,
    orgs_repo: OrgsRepo,
    request: Request,
    house: House,
    flat: Flat | None,
) -> RequestCardData:
    # карточку собирают обе стороны: кабинет жителя и кабинет УК. Отличаются
    # они правами на входе, а не содержимым заявки
    request_id = RequestId(request.id)
    photos = await requests_repo.list_photos(request_id)
    messages = await requests_repo.list_messages(request_id)
    authors = {
        UserId(user.id): user
        for user in await users_repo.list_by_ids(
            [UserId(message.author_user_id) for message in messages],
        )
    }
    group_sizes = await requests_repo.count_by_group(
        [] if request.group_id is None else [RequestGroupId(request.group_id)],
    )
    executor = (
        None
        if request.executor_user_id is None
        else await users_repo.get_by_id(UserId(request.executor_user_id))
    )
    return RequestCardData(
        request=request,
        house=house,
        org=None if house.org_id is None else await orgs_repo.get(OrgId(house.org_id)),
        flat=flat,
        issue_photos=[
            photo for photo in photos if photo.kind is RequestPhotoKind.ISSUE
        ],
        result_photos=[
            photo for photo in photos if photo.kind is RequestPhotoKind.RESULT
        ],
        timeline=await requests_repo.list_log(request_id),
        messages=[
            RequestMessageView(
                message=message,
                author=authors.get(UserId(message.author_user_id)),
            )
            for message in messages
        ],
        group_size=(
            0
            if request.group_id is None
            else group_sizes.get(RequestGroupId(request.group_id), 0)
        ),
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
    )


def _stated(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise InvalidRequest(EMPTY_DESCRIPTION)
    return stripped


def _stated_or_none(text: str | None) -> str | None:
    if text is None:
        return None
    stripped = text.strip()
    return stripped or None
