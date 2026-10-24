from datetime import UTC, datetime

from zheka.core import texts
from zheka.core.enums import (
    EventType,
    RequestActorRole,
    RequestChannel,
    RequestStatus,
)
from zheka.core.errors import (
    HOUSE_NOT_FOUND,
    REQUEST_NOT_FOUND,
    EntityNotFound,
    InvalidRequest,
    InvalidState,
)
from zheka.core.ids import AccessRequestId, AccessSlotId, OrgId, RequestId, UserId
from zheka.core.models import AccessRequest, House, Request
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.requests import RequestsService
from zheka.core.services.visit_card import VisitData, VisitWindow, visit_data
from zheka.core.services.visits.rules import (
    BAD_MINUTES,
    DUPLICATE_WINDOWS,
    MAX_MINUTES,
    MAX_WINDOWS,
    MIN_MINUTES,
    NOT_PERSONAL,
    NO_VISIT,
    PAST_WINDOW,
    REQUEST_CLOSED,
    VISIT_CANCELED,
    VISIT_NOT_FOUND,
    VISIT_REPLACED,
    VISIT_UNDER_WAY,
    WINDOWS_COUNT,
    WINDOW_NOT_FOUND,
    WINDOW_OFF_DATE,
    VisitDraft,
    visit_refusal,
)
from zheka.infra.database.repos.access import AccessRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.requests import OPEN_STATUSES, RequestsRepo


class VisitService:
    __slots__ = (
        "_access",
        "_events",
        "_houses",
        "_notifications",
        "_requests",
        "_requests_service",
    )

    def __init__(
        self,
        access_repo: AccessRepo,
        requests_repo: RequestsRepo,
        houses_repo: HousesRepo,
        events_service: EventsService,
        notifications_service: NotificationsService,
        requests_service: RequestsService,
    ) -> None:
        self._access = access_repo
        self._requests = requests_repo
        self._houses = houses_repo
        self._events = events_service
        self._notifications = notifications_service
        self._requests_service = requests_service

    async def propose(
        self,
        org_id: OrgId,
        request_id: RequestId,
        actor: UserId,
        draft: VisitDraft,
    ) -> VisitData:
        request = await self._requests.get_for_org(request_id, org_id)
        if request is None:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        await self._requests.lock(request)
        flat_id = request.flat_id
        refusal = visit_refusal(request)
        if refusal is not None or flat_id is None:
            raise InvalidState(refusal or NOT_PERSONAL)

        house = await self._houses.get(request.house_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        starts = sorted(house.to_utc(start) for start in draft.starts)
        if not 1 <= len(starts) <= MAX_WINDOWS:
            raise InvalidRequest(WINDOWS_COUNT)
        if not MIN_MINUTES <= draft.minutes <= MAX_MINUTES:
            raise InvalidRequest(BAD_MINUTES)
        if len(set(starts)) != len(starts):
            raise InvalidRequest(DUPLICATE_WINDOWS)
        if any(house.local(start).date() != draft.date for start in starts):
            raise InvalidRequest(WINDOW_OFF_DATE)
        now = datetime.now(UTC)
        if starts[0] <= now:
            raise InvalidRequest(PAST_WINDOW)

        previous = await self._access.current_visit(request.id)
        if previous is not None:
            await self._access.cancel(previous, now)
        visit = await self._access.create_request(
            org_id,
            request.house_id,
            f"Визит по заявке №{request.id}",
            draft.date,
            actor,
            request_id=request.id,
        )
        await self._access.add_slots(
            visit.id,
            [(start, 1, draft.minutes) for start in starts],
        )
        await self._access.add_targets(visit.id, [flat_id])
        await self._requests.add_message(
            request.id,
            actor,
            RequestActorRole.STAFF.value,
            texts.visit_proposed_note(
                draft.date,
                [
                    texts.visit_span(house.local(start), draft.minutes)
                    for start in starts
                ],
            ),
        )
        await self._events.record(
            EventType.VISIT_PROPOSED,
            user_id=actor,
            request_id=request.id,
            access_request_id=visit.id,
            windows=len(starts),
            replaced=None if previous is None else previous.id,
        )
        self._notifications.open_visit_card(request.id, visit.id)
        return await visit_data(self._access, visit)

    async def cancel(
        self,
        org_id: OrgId,
        request_id: RequestId,
        actor: UserId,
    ) -> None:
        request = await self._requests.get_for_org(request_id, org_id)
        if request is None:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        await self._requests.lock(request)
        visit = await self._access.current_visit(request.id)
        if visit is None or request.status is RequestStatus.DONE:
            raise EntityNotFound(NO_VISIT)
        await self._access.cancel(visit, datetime.now(UTC))
        await self._events.record(
            EventType.VISIT_CANCELED,
            user_id=actor,
            request_id=request.id,
            access_request_id=visit.id,
        )
        self._notifications.notify_author(
            request,
            texts.visit_canceled(request),
        )

    async def pick(
        self,
        user_id: UserId,
        request_id: RequestId,
        slot_id: AccessSlotId,
        channel: RequestChannel,
    ) -> VisitData:
        request = await self._own_request(user_id, request_id)
        await self._requests.lock(request)
        slot = await self._access.lock_visit_slot(slot_id)
        if slot is None:
            raise EntityNotFound(WINDOW_NOT_FOUND)
        visit = await self._access.get(slot.access_request_id)
        if visit.request_id != request.id:
            raise EntityNotFound(WINDOW_NOT_FOUND)
        await self._check_live(request, visit)

        current = await visit_data(self._access, visit)
        if current.slot_id == slot_id:
            return current
        now = datetime.now(UTC)
        if current.under_way(now):
            raise InvalidState(VISIT_UNDER_WAY)
        if slot.starts_at <= now:
            raise InvalidState(PAST_WINDOW)
        house = await self._houses.get(request.house_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)

        target = await self._access.visit_target(visit.id)
        await self._access.pick(target, slot_id, now)
        await self._events.record(
            EventType.VISIT_SLOT_PICKED,
            user_id=user_id,
            request_id=request.id,
            access_request_id=visit.id,
            slot_id=slot_id,
        )
        picked = await visit_data(self._access, visit)
        if picked.picked is not None:
            was = current.picked
            await self._requests_service.write(
                user_id,
                request.id,
                texts.visit_chosen(
                    _local_span(house, picked.picked),
                    None if was is None else _span(house, was),
                ),
                channel,
            )
        return picked

    async def decline(
        self,
        user_id: UserId,
        request_id: RequestId,
        visit_id: AccessRequestId,
        channel: RequestChannel,
    ) -> None:
        request = await self._own_request(user_id, request_id)
        visit = await self._access.find(visit_id)
        if visit is None or visit.request_id != request.id:
            raise EntityNotFound(VISIT_NOT_FOUND)
        await self._check_live(request, visit)

        target = await self._access.visit_target(visit.id)
        if target.slot_id is None and target.responded_at is not None:
            return
        now = datetime.now(UTC)
        if (await visit_data(self._access, visit)).under_way(now):
            raise InvalidState(VISIT_UNDER_WAY)
        await self._access.decline(target, now)
        await self._events.record(
            EventType.VISIT_DECLINED,
            user_id=user_id,
            request_id=request.id,
            access_request_id=visit.id,
        )
        await self._requests_service.write(
            user_id,
            request.id,
            texts.VISIT_NONE_FITS,
            channel,
        )

    async def _own_request(self, user_id: UserId, request_id: RequestId) -> Request:
        request = await self._requests.get(request_id)
        if request is None or request.author_user_id != user_id:
            raise EntityNotFound(REQUEST_NOT_FOUND)
        return request

    async def _check_live(self, request: Request, visit: AccessRequest) -> None:
        if request.status not in OPEN_STATUSES:
            raise InvalidState(REQUEST_CLOSED)
        if visit.canceled_at is not None:
            current = await self._access.current_visit(request.id)
            raise InvalidState(VISIT_CANCELED if current is None else VISIT_REPLACED)


def _span(house: House, window: VisitWindow) -> str:
    return texts.visit_span(house.local(window.starts_at), window.minutes)


def _local_span(house: House, window: VisitWindow) -> str:
    day = texts.short_day(house.local(window.starts_at).date())
    return f"{day}, {_span(house, window)}"
