from collections.abc import Sequence
from datetime import UTC, datetime

from zheka.base import ZhekaType
from zheka.core.enums import (
    EventType,
    OrgRole,
    RequestActorRole,
    RequestCategory,
    RequestChannel,
    RequestGroupStatus,
    RequestStatus,
)
from zheka.core.errors import EntityNotFound, InvalidRequest, InvalidState
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
    RequestGroup,
    User,
)
from zheka.core.services.events import EventsService
from zheka.core.services.request_groups import (
    GroupingService,
    complaint_sources,
    rules_of,
)
from zheka.core.services.request_status import check_transition, transition_path
from zheka.core.services.requests import RequestCardData, build_card, build_rows
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestFilters, RequestsRepo
from zheka.infra.database.repos.users import UsersRepo

REQUEST_NOT_FOUND = "Заявка не найдена"
GROUP_NOT_FOUND = "Группа заявок не найдена"
HOUSE_NOT_FOUND = "Дом не найден"
FLAT_NOT_FOUND = "Квартира не найдена"
EXECUTOR_NOT_FOUND = "Исполнитель не найден"
NOT_AN_EXECUTOR = "Заявку ведет исполнитель, а не сотрудник кабинета"
EMPTY_REPLY = "Напишите ответ жителю"
EMPTY_DESCRIPTION = "Опишите проблему"
GROUP_ALREADY_THERE = "Все заявки группы уже в этом статусе"
NO_CALLER_IDENTIFICATION = "Укажите квартиру или имя и телефон звонившего"


class AdminRequestRow(ZhekaType):
    request: Request
    house: House
    flat: Flat | None
    author: User | None
    executor: User | None
    has_photos: bool
    group_size: int


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


class AdminRequestsService:
    __slots__ = (
        "_events",
        "_grouping",
        "_houses",
        "_orgs",
        "_requests",
        "_users",
    )

    def __init__(
        self,
        requests_repo: RequestsRepo,
        houses_repo: HousesRepo,
        users_repo: UsersRepo,
        orgs_repo: OrgsRepo,
        grouping_service: GroupingService,
        events_service: EventsService,
    ) -> None:
        self._requests = requests_repo
        self._houses = houses_repo
        self._users = users_repo
        self._orgs = orgs_repo
        self._grouping = grouping_service
        self._events = events_service

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

    async def card(
        self,
        org_id: OrgId,
        request_id: RequestId,
    ) -> AdminRequestCardData:
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
        await self._move(request, target, comment, actor)
        return await self._card(request)

    async def reply(
        self,
        org_id: OrgId,
        request_id: RequestId,
        text: str,
        actor: UserId,
    ) -> AdminRequestCardData:
        request = await self._org_request(org_id, request_id)
        stated = text.strip()
        if not stated:
            raise InvalidRequest(EMPTY_REPLY)

        # ответ УК - транзакционное сообщение, его не выключают настройками;
        # саму отправку жителю делает блок 13
        await self._requests.add_message(
            RequestId(request.id),
            actor,
            RequestActorRole.STAFF.value,
            stated,
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
        member = await self._orgs.get_member(org_id, executor_user_id)
        # чужой пользователь неотличим от несуществующего
        if member is None:
            raise EntityNotFound(EXECUTOR_NOT_FOUND)
        if member.role is not OrgRole.EXECUTOR:
            raise InvalidRequest(NOT_AN_EXECUTOR)

        # назначение само по себе статуса не двигает: в работу заявку
        # переводит исполнитель, когда берет ее
        await self._requests.set_executor(request, executor_user_id)
        await self._events.record(
            EventType.REQUEST_ASSIGNED,
            user_id=actor,
            request_id=request_id,
            executor_user_id=executor_user_id,
        )
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
        members = await self._requests.list_for_group(RequestGroupId(group.id))
        # опоздавший участник, застрявший в NEW, пока группа ушла вперед
        # (группа остается OPEN сквозь ACCEPTED/IN_PROGRESS/ON_REVIEW, и
        # свежая заявка вступает в нее как в любую другую открытую группу),
        # идет через промежуточные статусы той же транзакцией - лог и
        # событие на каждый шаг. Участник, обогнавший цель, ломает вызов
        # целиком: transition_path поднимет InvalidState до первой записи
        paths = [(member, transition_path(member.status, target)) for member in members]
        if all(not path for _, path in paths):
            raise InvalidState(GROUP_ALREADY_THERE)

        for member, path in paths:
            await self._move_through(member, path, comment, actor)
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
        description = draft.description.strip()
        if not description:
            raise InvalidRequest(EMPTY_DESCRIPTION)
        caller_name = (draft.caller_name or "").strip() or None
        caller_phone = (draft.caller_phone or "").strip() or None
        # заявку по звонку должно быть чем привязать к дому: либо к квартире,
        # либо к тому, кто звонил - иначе ее некому показать и некому звонить
        if draft.flat_id is None and not (caller_name and caller_phone):
            raise InvalidRequest(NO_CALLER_IDENTIFICATION)

        flat = None
        if draft.flat_id is not None:
            flat = await self._houses.get_flat(draft.flat_id)
            if flat is None or flat.house_id != draft.house_id:
                raise EntityNotFound(FLAT_NOT_FOUND)

        # у заявки по звонку нет автора в сервисе, поэтому и обратного канала
        # тоже нет: бот не пишет первым тому, кто его не запускал. Закрывает
        # такую заявку УК - принимать работу некому
        request = await self._requests.create(
            draft.house_id,
            draft.flat_id,
            None,
            draft.category,
            description,
            RequestChannel.PHONE,
            None,
            None,
            is_staff_author=True,
            caller_name=caller_name,
            caller_phone=caller_phone,
        )
        await self._requests.add_log(
            RequestId(request.id),
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
        return await self._card(request)

    async def executors(self, org_id: OrgId) -> list[ExecutorView]:
        members = await self._orgs.list_members(org_id)
        executor_ids = [
            UserId(member.user_id)
            for member in members
            if member.role is OrgRole.EXECUTOR
        ]
        users = await self._users.list_by_ids(executor_ids)
        active = await self._requests.count_active_by_executor(org_id)
        return [
            ExecutorView(user=user, active_requests=active.get(UserId(user.id), 0))
            for user in users
        ]

    async def _move(
        self,
        request: Request,
        target: RequestStatus,
        comment: str | None,
        actor: UserId,
    ) -> None:
        current = request.status
        check_transition(
            current,
            target,
            RequestActorRole.STAFF,
            has_author=request.author_user_id is not None,
        )
        at = datetime.now(UTC)
        await self._requests.set_status(request, target, at)
        await self._requests.add_log(
            RequestId(request.id),
            current,
            target,
            actor,
            RequestActorRole.STAFF.value,
            at,
        )
        stated = None if comment is None else comment.strip()
        if stated:
            # пояснение к статусу житель видит там же, где ответы УК
            await self._requests.add_message(
                RequestId(request.id),
                actor,
                RequestActorRole.STAFF.value,
                stated,
            )
        await self._events.record(
            EventType.REQUEST_STATUS_CHANGED,
            user_id=actor,
            request_id=RequestId(request.id),
            **{"from": current.value, "to": target.value},
            by_role=RequestActorRole.STAFF.value,
        )

    async def _move_through(
        self,
        request: Request,
        path: Sequence[RequestStatus],
        comment: str | None,
        actor: UserId,
    ) -> None:
        # комментарий сопровождает только последний шаг - тот, что диспетчер
        # действительно попросил; промежуточные шаги опоздавшего участника не
        # плодят копии одного и того же пояснения
        last = len(path) - 1
        for index, target in enumerate(path):
            await self._move(request, target, comment if index == last else None, actor)

    async def _card(self, request: Request) -> AdminRequestCardData:
        house = await self._house_of(request)
        flat = (
            None
            if request.flat_id is None
            else await self._houses.get_flat(FlatId(request.flat_id))
        )
        return AdminRequestCardData(
            card=await build_card(
                self._requests,
                self._users,
                self._orgs,
                request,
                house,
                flat,
            ),
            author=(
                None
                if request.author_user_id is None
                else await self._users.get_by_id(UserId(request.author_user_id))
            ),
        )

    async def _group_card(self, group: RequestGroup) -> RequestGroupCardData:
        members = await self._requests.list_for_group(RequestGroupId(group.id))
        rows = await self._rows(members)
        # столько жалобщиков собрало группу: квартира, а у заявки про общее
        # имущество - сам житель. Тот же счет, что и у склейки
        sources = complaint_sources(members)
        house = await self._houses.get(HouseId(group.house_id))
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        return RequestGroupCardData(
            group=group,
            house=house,
            rows=rows,
            flats_count=len(sources),
        )

    async def _rows(self, requests: Sequence[Request]) -> list[AdminRequestRow]:
        # счетчики фото/группы и подгрузка квартир/исполнителей общие с
        # кабинетом жителя - build_rows считает их один раз для обоих
        base_rows = await build_rows(
            self._requests,
            self._houses,
            self._users,
            requests,
        )
        houses = {
            HouseId(house.id): house
            for house in await self._houses.list_by_ids(
                [HouseId(request.house_id) for request in requests],
            )
        }
        authors = {
            UserId(user.id): user
            for user in await self._users.list_by_ids(
                [
                    UserId(request.author_user_id)
                    for request in requests
                    if request.author_user_id is not None
                ],
            )
        }
        return [
            AdminRequestRow(
                request=row.request,
                house=houses[HouseId(row.request.house_id)],
                flat=row.flat,
                author=(
                    None
                    if row.request.author_user_id is None
                    else authors.get(row.request.author_user_id)
                ),
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

    async def _org_group(
        self,
        org_id: OrgId,
        group_id: RequestGroupId,
    ) -> RequestGroup:
        group = await self._requests.get_group_for_org(group_id, org_id)
        if group is None:
            raise EntityNotFound(GROUP_NOT_FOUND)
        return group

    async def _house_of(self, request: Request) -> House:
        house = await self._houses.get(HouseId(request.house_id))
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        return house
