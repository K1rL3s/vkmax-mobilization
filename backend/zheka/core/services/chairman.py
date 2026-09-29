from datetime import UTC, datetime, timedelta

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import EventType, NotificationCategory, ResidentStatus
from zheka.core.errors import (
    HOUSE_NOT_FOUND,
    EntityNotFound,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import HouseId, OrgId, UserId
from zheka.core.models import ChairmanHandover, Resident
from zheka.core.services.events import EventsService
from zheka.core.services.invites import issue_invite
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.chairman import ChairmanRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

HANDOVER_HOURS = 48
NOT_A_CHAIRMAN = "Передать роль может только действующий председатель совета дома"
HANDOVER_NOT_FOUND = "Ссылка на передачу роли не найдена"
HANDOVER_CLOSED = "Ссылка больше не действует: истекла, отозвана или уже использована"
ISSUER_GONE = "Выдавший ссылку больше не председатель этого дома"
NOT_A_NEIGHBOUR = "Принять роль может только житель этого дома"
VERIFY_FIRST = "Сначала подтвердите свою квартиру"
SELF_HANDOVER = "Вы уже председатель этого дома"


class ChairmanOffer(ZhekaType):
    code: str
    address: str
    org_id: OrgId | None
    issuer_id: UserId
    from_name: str
    to_name: str


class ChairmanService:
    __slots__ = (
        "_events",
        "_handovers",
        "_houses",
        "_notifications",
        "_orgs",
        "_residents",
        "_users",
    )

    def __init__(
        self,
        chairman_repo: ChairmanRepo,
        residents_repo: ResidentsRepo,
        houses_repo: HousesRepo,
        users_repo: UsersRepo,
        orgs_repo: OrgsRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> None:
        self._handovers = chairman_repo
        self._residents = residents_repo
        self._houses = houses_repo
        self._users = users_repo
        self._orgs = orgs_repo
        self._notifications = notifications_service
        self._events = events_service

    async def open_handover(
        self,
        user_id: UserId,
        house_id: HouseId,
    ) -> ChairmanHandover | None:
        await self._acting_chairman(user_id, house_id)
        handover = await self._handovers.get_open(house_id, datetime.now(UTC))
        if handover is None or handover.created_by != user_id:
            return None
        return handover

    async def create_handover(
        self,
        user_id: UserId,
        house_id: HouseId,
    ) -> ChairmanHandover:
        await self._acting_chairman(user_id, house_id)
        now = datetime.now(UTC)
        await self._handovers.close_open(house_id, now)
        handover = await issue_invite(
            lambda code: self._handovers.create(
                code=code,
                house_id=house_id,
                created_by=user_id,
                expires_at=now + timedelta(hours=HANDOVER_HOURS),
            ),
        )
        await self._events.record(
            EventType.CHAIRMAN_HANDOVER_CREATED,
            user_id=user_id,
            house_id=house_id,
        )
        return handover

    async def revoke_handover(self, user_id: UserId, house_id: HouseId) -> None:
        await self._acting_chairman(user_id, house_id)
        await self._handovers.close_open(house_id, datetime.now(UTC))

    async def offer(self, user_id: UserId, code: str) -> ChairmanOffer:
        handover = await self._handovers.get(code)
        if handover is None:
            raise EntityNotFound(HANDOVER_NOT_FOUND)
        _, offer = await self._addressed(handover, user_id)
        await self._taker(handover, user_id)
        return offer

    async def accept(self, user_id: UserId, code: str) -> ChairmanOffer:
        handover = await self._locked(code)
        issuer, offer = await self._addressed(handover, user_id)
        taker = await self._taker(handover, user_id)

        await self._residents.set_chairman(issuer, value=False)
        await self._residents.set_chairman(taker, value=True)
        await self._handovers.decide(handover, datetime.now(UTC), user_id)
        await self._events.record(
            EventType.CHAIRMAN_HANDED_OVER,
            user_id=user_id,
            house_id=handover.house_id,
            handed_by=handover.created_by,
        )
        await self._announce(
            offer,
            texts.chairman_accepted(offer.to_name, offer.address),
        )
        return offer

    async def decline(self, user_id: UserId, code: str) -> ChairmanOffer:
        handover = await self._locked(code)
        _, offer = await self._addressed(handover, user_id)

        await self._handovers.decide(handover, datetime.now(UTC), None)
        await self._announce(
            offer,
            texts.chairman_declined(offer.to_name, offer.address),
        )
        return offer

    async def _locked(self, code: str) -> ChairmanHandover:
        handover = await self._handovers.lock(code)
        if handover is None:
            raise EntityNotFound(HANDOVER_NOT_FOUND)
        return handover

    async def _addressed(
        self,
        handover: ChairmanHandover,
        user_id: UserId,
    ) -> tuple[Resident, ChairmanOffer]:
        if not handover.is_open(datetime.now(UTC)):
            raise InvalidState(HANDOVER_CLOSED)
        if user_id == handover.created_by:
            raise InvalidState(SELF_HANDOVER)

        house = await self._houses.get(handover.house_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)

        issuer = await self._residents.get_for_house(
            handover.created_by,
            handover.house_id,
        )
        if issuer is None or not issuer.is_chairman:
            raise InvalidState(ISSUER_GONE)

        return issuer, ChairmanOffer(
            code=handover.code,
            address=house.address,
            org_id=house.org_id,
            issuer_id=handover.created_by,
            from_name=await self._name(handover.created_by),
            to_name=await self._name(user_id),
        )

    async def _taker(self, handover: ChairmanHandover, user_id: UserId) -> Resident:
        taker = await self._residents.get_for_house(user_id, handover.house_id)
        if taker is None:
            raise NotEnoughRights(NOT_A_NEIGHBOUR)
        if taker.status is ResidentStatus.BLOCKED:
            raise NotEnoughRights(texts.blocked_detail(taker.block_reason))
        if taker.verified_at is None:
            raise NotEnoughRights(VERIFY_FIRST)
        return taker

    async def _acting_chairman(self, user_id: UserId, house_id: HouseId) -> Resident:
        resident = await self._residents.get_for_house(user_id, house_id)
        if resident is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        if resident.status is ResidentStatus.BLOCKED:
            raise NotEnoughRights(texts.blocked_detail(resident.block_reason))
        if not resident.is_chairman:
            raise NotEnoughRights(NOT_A_CHAIRMAN)
        return resident

    async def _name(self, user_id: UserId) -> str:
        user = await self._users.get_by_id(user_id)
        return "" if user is None else user.name

    async def _announce(self, offer: ChairmanOffer, text: str) -> None:
        recipients = [offer.issuer_id]
        if offer.org_id is not None:
            members = await self._orgs.list_members(offer.org_id)
            recipients.extend(
                member.user_id
                for member in members
                if member.role.is_staff and member.user_id != offer.issuer_id
            )
        self._notifications.notify_users(
            recipients,
            text,
            category=NotificationCategory.REQUESTS,
            mandatory=True,
        )
