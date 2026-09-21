from zheka.core import texts
from zheka.core.enums import EventType, NotificationCategory, ResidentStatus
from zheka.core.errors import EntityNotFound, InvalidRequest, InvalidState
from zheka.core.ids import OrgId, ResidentId, UserId
from zheka.core.models import Resident
from zheka.core.services.events import EventsService
from zheka.core.services.houses import HouseResidentView
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo


class ModerationService:
    __slots__ = ("_events", "_houses", "_notifications", "_residents", "_users")

    def __init__(
        self,
        residents_repo: ResidentsRepo,
        users_repo: UsersRepo,
        houses_repo: HousesRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> None:
        self._residents = residents_repo
        self._users = users_repo
        self._houses = houses_repo
        self._notifications = notifications_service
        self._events = events_service

    async def block(
        self, org_id: OrgId, resident_id: ResidentId, reason: str, by: UserId
    ) -> HouseResidentView:
        stated = _require_reason(reason)
        resident = await self._get_resident(org_id, resident_id)
        # председателя блокирует только снятие председательства
        if resident.is_chairman:
            raise InvalidState("Нельзя заблокировать председателя совета дома")

        # блокировка ничего не удаляет: заявки, показания и голоса остаются
        await self._residents.set_status(resident, ResidentStatus.BLOCKED, stated)
        await self._events.record(
            EventType.RESIDENT_BLOCKED,
            user_id=by,
            resident_id=resident_id,
            reason=stated,
        )
        self._notify(
            resident, texts.resident_blocked(await self._address(resident), stated)
        )
        return await self._view(resident)

    async def unblock(
        self, org_id: OrgId, resident_id: ResidentId, by: UserId
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
        self, org_id: OrgId, resident_id: ResidentId, reason: str, by: UserId
    ) -> HouseResidentView:
        stated = _require_reason(reason)
        resident = await self._get_resident(org_id, resident_id)
        if resident.verified_at is None:
            raise InvalidState("Квартира жителя не подтверждена")

        # привязка к дому остается, снимается подтверждение квартиры и вместе
        # с ним председательство: председателем бывает только подтвержденный
        await self._residents.revoke_verification(resident)
        await self._events.record(
            EventType.FLAT_VERIFICATION_REVOKED,
            user_id=by,
            resident_id=resident_id,
            reason=stated,
        )
        return await self._view(resident)

    async def set_chairman(
        self, org_id: OrgId, resident_id: ResidentId, value: bool
    ) -> HouseResidentView:
        resident = await self._get_resident(org_id, resident_id)
        if value:
            if resident.verified_at is None:
                raise InvalidState(
                    "Председателем становится житель с подтвержденной квартирой"
                )
            # председатель в доме один, поэтому прошлый снимается той же
            # транзакцией
            await self._residents.clear_chairman(resident.house_id)
        await self._residents.set_chairman(resident, value)
        return await self._view(resident)

    async def _address(self, resident: Resident) -> str:
        house = await self._houses.get(resident.house_id)
        return "" if house is None else house.address

    def _notify(self, resident: Resident, text: str) -> None:
        # закрытый и открытый доступ житель должен увидеть при любых
        # настройках, поэтому сообщение обязательное
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


def _require_reason(reason: str) -> str:
    # строка из пробелов - это пустая причина, и она не должна доехать до
    # уведомления жителю
    stripped = reason.strip()
    if not stripped:
        raise InvalidRequest("Укажите причину")
    return stripped
