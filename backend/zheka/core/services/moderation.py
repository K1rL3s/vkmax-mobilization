from zheka.core import texts
from zheka.core.enums import (
    EventType,
    NotificationCategory,
    ResidentRole,
    ResidentStatus,
)
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import OrgId, ResidentId, UserId
from zheka.core.models import Resident
from zheka.core.services.chairman import OWNERS_ONLY
from zheka.core.services.events import EventsService
from zheka.core.services.houses import HouseResidentView
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

SPARE_REVIEWERS = "В демо-УК можно ограничить только модельных жителей"
SPARE_CHAIRMAN = "В демо-УК можно снять или сменить только модельного председателя"


class ModerationService:
    __slots__ = (
        "_events",
        "_houses",
        "_notifications",
        "_orgs",
        "_residents",
        "_users",
    )

    def __init__(
        self,
        residents_repo: ResidentsRepo,
        users_repo: UsersRepo,
        houses_repo: HousesRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
        orgs_repo: OrgsRepo,
    ) -> None:
        self._residents = residents_repo
        self._users = users_repo
        self._houses = houses_repo
        self._notifications = notifications_service
        self._events = events_service
        self._orgs = orgs_repo

    async def block(
        self,
        org_id: OrgId,
        resident_id: ResidentId,
        reason: str,
        by: UserId,
    ) -> HouseResidentView:
        stated = _require_reason(reason)
        resident = await self._get_resident(org_id, resident_id)
        await self._spare_reviewers(org_id, resident, by)
        if resident.is_chairman:
            raise InvalidState("Нельзя заблокировать председателя совета дома")
        contact = await self._contact(org_id)

        await self._residents.set_status(resident, ResidentStatus.BLOCKED, stated)
        await self._events.record(
            EventType.RESIDENT_BLOCKED,
            user_id=by,
            resident_id=resident_id,
            reason=stated,
        )
        self._notify(
            resident,
            texts.resident_blocked(await self._address(resident), stated, contact),
        )
        return await self._view(resident)

    async def unblock(
        self,
        org_id: OrgId,
        resident_id: ResidentId,
        by: UserId,
    ) -> HouseResidentView:
        resident = await self._get_resident(org_id, resident_id)
        await self._residents.set_status(resident, ResidentStatus.ACTIVE, None)
        await self._events.record(
            EventType.RESIDENT_UNBLOCKED,
            user_id=by,
            resident_id=resident_id,
            reason=None,
        )
        self._notify(resident, texts.resident_unblocked(await self._address(resident)))
        return await self._view(resident)

    async def revoke_verification(
        self,
        org_id: OrgId,
        resident_id: ResidentId,
        reason: str,
        by: UserId,
    ) -> HouseResidentView:
        stated = _require_reason(reason)
        resident = await self._get_resident(org_id, resident_id)
        await self._spare_reviewers(org_id, resident, by)
        if resident.verified_at is None:
            raise InvalidState("Квартира жителя не подтверждена")
        contact = await self._contact(org_id)

        await self._residents.revoke_verification(resident)
        await self._events.record(
            EventType.FLAT_VERIFICATION_REVOKED,
            user_id=by,
            resident_id=resident_id,
            reason=stated,
        )
        self._notify(
            resident,
            texts.flat_verification_revoked(
                await self._address(resident),
                stated,
                contact,
            ),
        )
        return await self._view(resident)

    async def set_chairman(
        self,
        org_id: OrgId,
        resident_id: ResidentId,
        value: bool,
        by: UserId,
    ) -> HouseResidentView:
        resident = await self._get_resident(org_id, resident_id)
        if value:
            if resident.verified_at is None:
                raise InvalidState(
                    "Председателем становится житель с подтвержденной квартирой",
                )
            if resident.role is not ResidentRole.OWNER:
                raise InvalidState(OWNERS_ONLY)
            chairman = await self._residents.get_chairman(resident.house_id)
            if chairman is not None and chairman.id != resident.id:
                await self._spare_reviewers(org_id, chairman, by, SPARE_CHAIRMAN)
            await self._residents.clear_chairman(resident.house_id)
        elif resident.is_chairman:
            await self._spare_reviewers(org_id, resident, by, SPARE_CHAIRMAN)
        await self._residents.set_chairman(resident, value)
        return await self._view(resident)

    async def _address(self, resident: Resident) -> str:
        house = await self._houses.get(resident.house_id)
        return "" if house is None else house.address

    def _notify(self, resident: Resident, text: str) -> None:
        self._notifications.notify_user(
            resident.user_id,
            text,
            category=NotificationCategory.REQUESTS,
            mandatory=True,
        )

    async def _get_resident(self, org_id: OrgId, resident_id: ResidentId) -> Resident:
        resident = await self._residents.get_for_org(resident_id, org_id)
        if resident is None:
            raise EntityNotFound("Житель не найден")
        return resident

    async def _view(self, resident: Resident) -> HouseResidentView:
        user = await self._users.get_by_id(resident.user_id)
        if user is None:
            raise EntityNotFound("Пользователь не найден")
        flat = (
            None
            if resident.flat_id is None
            else await self._houses.get_flat(resident.flat_id)
        )
        return HouseResidentView(resident=resident, user=user, flat=flat)

    async def _contact(self, org_id: OrgId) -> str:
        org = await self._orgs.get_existing(org_id)
        return texts.org_contact(org.name, org.phone)

    async def _spare_reviewers(
        self,
        org_id: OrgId,
        resident: Resident,
        by: UserId,
        refusal: str = SPARE_REVIEWERS,
    ) -> None:
        if (
            resident.user_id == by
            or not (await self._orgs.get_existing(org_id)).is_demo
        ):
            return
        user = await self._users.get_by_id(resident.user_id)
        if user is not None and user.max_user_id > 0:
            raise NotEnoughRights(refusal)


def _require_reason(reason: str) -> str:
    stripped = reason.strip()
    if not stripped:
        raise InvalidRequest("Укажите причину")
    return stripped
