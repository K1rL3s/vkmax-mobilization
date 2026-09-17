from collections.abc import Collection, Sequence
from datetime import UTC, datetime, timedelta

from zheka.base import ZhekaType
from zheka.core.enums import (
    EventType,
    RequestActorRole,
    RequestCategory,
    RequestChannel,
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
    Request,
    RequestMessage,
    RequestPhoto,
    RequestStatusLog,
    Resident,
    User,
)
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

# потолок вложений в одном сообщении MAX, он же потолок фото у заявки
MAX_PHOTOS = 12
# заявку, оставленную на приемке, закрывает планировщик блока 18
AUTO_CLOSE_AFTER = timedelta(hours=48)

BLOCKED = "Вы заблокированы в этом доме"
NOT_A_RESIDENT = "Дом не найден"
REQUEST_NOT_FOUND = "Заявка не найдена"
FLAT_NOT_FOUND = "Квартира не найдена"
GROUP_NOT_FOUND = "Группа заявок не найдена"
GROUP_CLOSED = "Группа заявок уже закрыта"
GROUP_OTHER_CATEGORY = "Группа заявок собрана по другой категории"
EMPTY_DESCRIPTION = "Опишите проблему"
TOO_MANY_PHOTOS = f"К заявке можно приложить не больше {MAX_PHOTOS} фото"
RATE_NOT_DONE = "Оценку ставят выполненной заявке"
RATED_ALREADY = "Оценка уже поставлена"
REPEAT_NOT_DONE = "Повторную заявку подают по выполненной"


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
    flat: Flat | None
    issue_photos: Sequence[RequestPhoto]
    result_photos: Sequence[RequestPhoto]
    timeline: Sequence[RequestStatusLog]
    messages: Sequence[RequestMessageView]
    group_size: int
    executor: User | None
    can_review: bool
    can_rate: bool


class RequestsService:
    __slots__ = (
        "_events",
        "_files",
        "_houses",
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
        events_service: EventsService,
    ) -> None:
        self._requests = requests_repo
        self._houses = houses_repo
        self._residents = residents_repo
        self._users = users_repo
        self._orgs = orgs_repo
        self._files = files_service
        self._events = events_service

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
        return await self._card(request, house, flat)

    async def repeat(
        self,
        user_id: UserId,
        request_id: RequestId,
        description: str | None,
        photos: Sequence[str],
    ) -> RequestCardData:
        parent = await self._own_request(user_id, request_id)
        if parent.status is not RequestStatus.DONE:
            raise InvalidState(REPEAT_NOT_DONE)

        house_id = HouseId(parent.house_id)
        await self._active_resident(user_id, house_id)
        house = await self._get_house(house_id)
        # описание и фото у повтора свои, остальное - копия родителя: житель
        # жалуется на ту же проблему в той же квартире
        text = _stated(parent.description if description is None else description)
        checked = self._checked_photos(photos)
        flat = (
            None
            if parent.flat_id is None
            else await self._houses.get_flat(FlatId(parent.flat_id))
        )

        request = await self._requests.create(
            house_id,
            None if parent.flat_id is None else FlatId(parent.flat_id),
            user_id,
            parent.category,
            text,
            RequestChannel.MINIAPP,
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
            channel=RequestChannel.MINIAPP.value,
            has_photo=bool(checked),
            is_repeat=True,
            parent_request_id=RequestId(parent.id),
        )
        return await self._card(request, house, flat)

    async def rate(
        self,
        user_id: UserId,
        request_id: RequestId,
        rating: int,
        feedback: str | None,
    ) -> RequestCardData:
        request = await self._own_request(user_id, request_id)
        await self._active_resident(user_id, HouseId(request.house_id))
        if request.status is not RequestStatus.DONE:
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

    async def get_card(self, user_id: UserId, request_id: RequestId) -> RequestCardData:
        request = await self._own_request(user_id, request_id)
        house = await self._get_house(HouseId(request.house_id))
        flat = (
            None
            if request.flat_id is None
            else await self._houses.get_flat(FlatId(request.flat_id))
        )
        return await self._card(request, house, flat)

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
        photo_counts = await self._requests.count_photos(
            [RequestId(request.id) for request in requests],
        )
        group_sizes = await self._requests.count_by_group(
            {
                RequestGroupId(request.group_id)
                for request in requests
                if request.group_id is not None
            },
        )
        flats = await self._flats_by_id(
            [
                FlatId(request.flat_id)
                for request in requests
                if request.flat_id is not None
            ],
        )
        executors = await self._users_by_id(
            [
                UserId(request.executor_user_id)
                for request in requests
                if request.executor_user_id is not None
            ],
        )
        rows = [
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
        return rows, total

    async def _card(
        self,
        request: Request,
        house: House,
        flat: Flat | None,
    ) -> RequestCardData:
        request_id = RequestId(request.id)
        photos = await self._requests.list_photos(request_id)
        messages = await self._requests.list_messages(request_id)
        authors = await self._users_by_id(
            [UserId(message.author_user_id) for message in messages],
        )
        group_sizes = await self._requests.count_by_group(
            [] if request.group_id is None else [RequestGroupId(request.group_id)],
        )
        executor = (
            None
            if request.executor_user_id is None
            else await self._users.get_by_id(UserId(request.executor_user_id))
        )
        return RequestCardData(
            request=request,
            house=house,
            flat=flat,
            issue_photos=[
                photo for photo in photos if photo.kind is RequestPhotoKind.ISSUE
            ],
            result_photos=[
                photo for photo in photos if photo.kind is RequestPhotoKind.RESULT
            ],
            timeline=await self._requests.list_log(request_id),
            messages=[
                RequestMessageView(
                    message=message,
                    author=authors.get(message.author_user_id),
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
            can_rate=request.status is RequestStatus.DONE and request.rating is None,
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

    async def _flats_by_id(
        self,
        flat_ids: Collection[FlatId],
    ) -> dict[FlatId, Flat]:
        return {
            FlatId(flat.id): flat
            for flat in await self._houses.list_flats_by_ids(flat_ids)
        }

    async def _users_by_id(
        self,
        user_ids: Collection[UserId],
    ) -> dict[UserId, User]:
        return {
            UserId(user.id): user for user in await self._users.list_by_ids(user_ids)
        }


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
