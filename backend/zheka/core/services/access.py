from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import EventType, ResidentStatus
from zheka.core.errors import (
    FLAT_NOT_FOUND,
    HOUSE_NOT_FOUND,
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import AccessRequestId, AccessSlotId, FlatId, HouseId, OrgId, UserId
from zheka.core.models import AccessRequest, AccessSlot, AccessTarget
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.reception import as_utc
from zheka.infra.database.repos.access import AccessRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.residents import ResidentsRepo

REQUEST_NOT_FOUND = "Запрос доступа не найден"
SLOT_NOT_FOUND = "Слот не найден"
SLOT_FULL = "В этом окне больше нет мест"
EMPTY_REASON = "Напишите, зачем нужен доступ в квартиру"
NO_SLOTS = "Добавьте хотя бы одно окно"
NO_FLATS = "Выберите хотя бы одну квартиру"
BAD_CAPACITY = "В окно должна помещаться хотя бы одна квартира"
DUPLICATE_SLOTS = "Окна доступа начинаются в одно и то же время"
PAST_DATE = "День доступа уже прошел"
SLOT_OFF_DATE = "Окна доступа должны быть в тот же день"


class AccessSlotData(ZhekaType):
    slot: AccessSlot
    taken: int


class AccessRequestData(ZhekaType):
    request: AccessRequest
    address: str
    slots: list[AccessSlotData]
    responded_count: int
    targets_count: int
    # только в ответах жителю
    my_flat_id: FlatId | None = None
    my_slot_id: AccessSlotId | None = None


class AccessTargetData(ZhekaType):
    target: AccessTarget
    flat_number: str


class AccessGridData(ZhekaType):
    request: AccessRequestData
    targets: list[AccessTargetData]
    # заполняет только create: квартире без подтвержденного жителя некому
    # написать, поэтому ячейки у нее нет
    flats_without_residents: Sequence[FlatId] = ()


class AccessSlotDraft(ZhekaType):
    starts_at: datetime
    capacity: int


class AccessRequestDraft(ZhekaType):
    house_id: HouseId
    reason: str
    date: date
    flat_ids: Sequence[FlatId]
    slots: Sequence[AccessSlotDraft]


class AccessService:
    __slots__ = ("_access", "_events", "_houses", "_notifications", "_residents")

    def __init__(
        self,
        access_repo: AccessRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        events_service: EventsService,
        notifications_service: NotificationsService,
    ) -> None:
        self._access = access_repo
        self._houses = houses_repo
        self._residents = residents_repo
        self._events = events_service
        self._notifications = notifications_service

    async def create(
        self, org_id: OrgId, user_id: UserId, draft: AccessRequestDraft
    ) -> AccessGridData:
        reason = draft.reason.strip()
        if not reason:
            raise InvalidRequest(EMPTY_REASON)
        if not draft.slots:
            raise InvalidRequest(NO_SLOTS)
        if not draft.flat_ids:
            raise InvalidRequest(NO_FLATS)
        if any(slot.capacity < 1 for slot in draft.slots):
            raise InvalidRequest(BAD_CAPACITY)
        if draft.date < datetime.now(UTC).date():
            raise InvalidRequest(PAST_DATE)
        starts = [as_utc(slot.starts_at) for slot in draft.slots]
        if len(set(starts)) != len(starts):
            raise InvalidRequest(DUPLICATE_SLOTS)
        # сетка дня, у которой окна стоят в другом дне, не сетка ни для кого
        if any(start.date() != draft.date for start in starts):
            raise InvalidRequest(SLOT_OFF_DATE)

        house = await self._houses.get_for_org(draft.house_id, org_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)

        flat_ids = list(dict.fromkeys(draft.flat_ids))
        flats = await self._houses.list_flats_by_ids(flat_ids)
        of_house = {flat.id for flat in flats if flat.house_id == draft.house_id}
        if any(flat_id not in of_house for flat_id in flat_ids):
            raise EntityNotFound(FLAT_NOT_FOUND)

        residents = await self._residents.list_verified_for_house(draft.house_id)
        with_residents = {
            resident.flat_id for resident in residents if resident.flat_id is not None
        }
        targeted = [flat_id for flat_id in flat_ids if flat_id in with_residents]
        skipped = [flat_id for flat_id in flat_ids if flat_id not in with_residents]

        request = await self._access.create_request(
            org_id, draft.house_id, reason, draft.date, user_id
        )
        access_request_id = request.id
        await self._access.add_slots(
            access_request_id,
            [
                (starts_at, slot.capacity)
                for starts_at, slot in zip(starts, draft.slots, strict=True)
            ],
        )
        await self._access.add_targets(access_request_id, targeted)

        await self._events.record(
            EventType.ACCESS_REQUEST_SENT,
            user_id=user_id,
            access_request_id=access_request_id,
            flats_count=len(targeted),
        )
        self._notifications.open_access_slots(access_request_id)

        grid = await self.grid(org_id, access_request_id)
        return replace(grid, flats_without_residents=skipped)

    async def grid(
        self, org_id: OrgId, access_request_id: AccessRequestId
    ) -> AccessGridData:
        request = await self._access.get_for_org(access_request_id, org_id)
        if request is None:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        [row] = await self._decorate([request], {})
        targets = await self._access.list_targets(access_request_id)
        numbers = {
            flat.id: flat.number
            for flat in await self._houses.list_flats_by_ids(
                {target.flat_id for target in targets}
            )
        }
        return AccessGridData(
            request=row,
            targets=[
                AccessTargetData(
                    target=target, flat_number=numbers[FlatId(target.flat_id)]
                )
                for target in targets
            ],
        )

    async def pick(
        self, user_id: UserId, access_request_id: AccessRequestId, slot_id: AccessSlotId
    ) -> AccessRequestData:
        target = await self._target(user_id, access_request_id)
        # слот чужого запроса доступа сюда не проходит: выборка сужена
        # запросом, в котором стоит ячейка жителя
        slot = await self._access.lock_slot(access_request_id, slot_id)
        if slot is None:
            raise EntityNotFound(SLOT_NOT_FOUND)

        # повторный выбор того же окна ничего не пишет и не дает события
        if target.slot_id != slot_id:
            if await self._access.count_picks(slot_id) >= slot.capacity:
                raise InvalidState(SLOT_FULL)
            await self._access.pick(target, slot_id, datetime.now(UTC))
            await self._events.record(
                EventType.ACCESS_SLOT_PICKED,
                user_id=user_id,
                access_request_id=access_request_id,
                slot_id=slot_id,
            )

        return await self._view(access_request_id, target)

    async def list_for_org(
        self, org_id: OrgId, house_id: HouseId | None
    ) -> list[AccessRequestData]:
        if (
            house_id is not None
            and await self._houses.get_for_org(house_id, org_id) is None
        ):
            raise EntityNotFound(HOUSE_NOT_FOUND)
        requests = await self._access.list_for_org(org_id, house_id)
        return await self._decorate(requests, {})

    async def list_for_resident(
        self, flat_id: FlatId | None
    ) -> list[AccessRequestData]:
        # житель без подтвержденной квартиры не адресат ни одного запроса
        if flat_id is None:
            return []
        pairs = await self._access.list_for_flat(flat_id)
        mine = {request.id: target for request, target in pairs}
        return await self._decorate([request for request, _ in pairs], mine)

    async def _decorate(
        self,
        requests: Sequence[AccessRequest],
        mine: dict[AccessRequestId, AccessTarget],
    ) -> list[AccessRequestData]:
        if not requests:
            return []
        request_ids = {request.id for request in requests}
        houses = {
            house.id: house
            for house in await self._houses.list_by_ids(
                {request.house_id for request in requests}
            )
        }
        slots = await self._access.list_slots(request_ids)
        taken = await self._access.picks_by_slot(request_ids)
        counters = await self._access.counters(request_ids)

        rows = []
        for request in requests:
            request_id = request.id
            responded, total = counters.get(request_id, (0, 0))
            target = mine.get(request_id)
            rows.append(
                AccessRequestData(
                    request=request,
                    address=houses[request.house_id].address,
                    slots=[
                        AccessSlotData(slot=slot, taken=taken.get(slot.id, 0))
                        for slot in slots
                        if slot.access_request_id == request_id
                    ],
                    responded_count=responded,
                    targets_count=total,
                    my_flat_id=None if target is None else target.flat_id,
                    my_slot_id=(None if target is None else target.slot_id),
                )
            )
        return rows

    async def resident_view(
        self, user_id: UserId, access_request_id: AccessRequestId
    ) -> AccessRequestData:
        target = await self._target(user_id, access_request_id)
        return await self._view(access_request_id, target)

    async def _target(
        self, user_id: UserId, access_request_id: AccessRequestId
    ) -> AccessTarget:
        residencies = {
            resident.flat_id: resident
            for resident in await self._residents.list_for_user(user_id)
            if resident.flat_id is not None and resident.verified_at is not None
        }
        target = await self._access.target_for_flats(
            access_request_id, residencies.keys()
        )
        if target is None:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        # сначала ячейка, потом блокировка: чужому достается 404, из которого
        # он ничего не узнает, а заблокированному - прямой отказ с причиной,
        # которую УК ему уже назвала
        resident = residencies[target.flat_id]
        if resident.status is ResidentStatus.BLOCKED:
            raise NotEnoughRights(texts.blocked_detail(resident.block_reason))
        return target

    async def _view(
        self, access_request_id: AccessRequestId, target: AccessTarget
    ) -> AccessRequestData:
        request = await self._access.get(access_request_id)
        [row] = await self._decorate([request], {access_request_id: target})
        return row
