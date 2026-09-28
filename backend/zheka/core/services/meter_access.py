from datetime import date, datetime

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import ResidentStatus, TariffZone
from zheka.core.errors import FLAT_NOT_FOUND, EntityNotFound, NotEnoughRights
from zheka.core.ids import FlatId, MeterId, UserId
from zheka.core.models import Flat, House, Meter, Resident
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

NOT_VERIFIED = "Подтвердите квартиру, чтобы работать со счетчиками"
CANNOT_MANAGE_METER = (
    "Добавлять и редактировать счетчики может собственник или сотрудник УК"
)


class MeterCard(ZhekaType):
    meter: Meter
    can_submit: bool
    verification_expired: bool
    last_period: date | None
    last_values: dict[TariffZone, int] | None
    prior_period: date | None
    prior_values: dict[TariffZone, int] | None


def zones_of(raw: dict[str, int]) -> dict[TariffZone, int]:
    return {TariffZone(key): value for key, value in raw.items()}


class MeterAccess:
    __slots__ = ("_houses", "_meters", "_orgs", "_residents")

    def __init__(
        self,
        meters_repo: MetersRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        orgs_repo: OrgsRepo,
    ) -> None:
        self._meters = meters_repo
        self._houses = houses_repo
        self._residents = residents_repo
        self._orgs = orgs_repo

    async def get_meter(self, meter_id: MeterId) -> Meter:
        meter = await self._meters.get(meter_id)
        if meter is None:
            raise EntityNotFound("Счетчик не найден")
        return meter

    async def resident_of_flat(
        self,
        user_id: UserId,
        flat_id: FlatId,
    ) -> Resident | None:
        residents = await self._residents.list_for_flat(flat_id)
        return next(
            (resident for resident in residents if resident.user_id == user_id),
            None,
        )

    async def verified_resident(self, user_id: UserId, flat_id: FlatId) -> Resident:
        resident = await self.resident_of_flat(user_id, flat_id)
        if resident is None:
            raise EntityNotFound(FLAT_NOT_FOUND)
        if resident.status is ResidentStatus.BLOCKED:
            raise NotEnoughRights(texts.blocked_detail(resident.block_reason))
        if resident.verified_at is None:
            raise NotEnoughRights(NOT_VERIFIED)
        return resident

    async def can_manage_meter(self, user_id: UserId, flat_id: FlatId) -> None:
        resident = await self.resident_of_flat(user_id, flat_id)
        if resident is not None:
            if resident.status is ResidentStatus.BLOCKED:
                raise NotEnoughRights(texts.blocked_detail(resident.block_reason))
            if resident.verified_at is not None and resident.can_see_charges:
                return

        house = await self.house_of_flat(flat_id)
        if house.org_id is not None:
            member = await self._orgs.get_member(house.org_id, user_id)
            if member is not None and member.role.is_staff:
                return

        if resident is not None:
            raise NotEnoughRights(CANNOT_MANAGE_METER)
        raise EntityNotFound(FLAT_NOT_FOUND)

    async def meter_card(self, meter: Meter, now: datetime) -> MeterCard:
        today = (await self.house_of_flat(meter.flat_id)).local(now).date()
        last = await self._meters.list_readings(meter.id, 1)
        last_reading = last[0] if last else None
        prior = (
            None
            if last_reading is None
            else await self._meters.previous_reading(meter.id, last_reading.period)
        )
        expired = (
            meter.next_verification_date is not None
            and meter.next_verification_date < today
        )
        return MeterCard(
            meter=meter,
            can_submit=not expired,
            verification_expired=expired,
            last_period=None if last_reading is None else last_reading.period,
            last_values=(
                None if last_reading is None else zones_of(last_reading.values)
            ),
            prior_period=None if prior is None else prior.period,
            prior_values=None if prior is None else zones_of(prior.values),
        )

    async def get_flat(self, flat_id: FlatId) -> Flat:
        flat = await self._houses.get_flat(flat_id)
        if flat is None:
            raise EntityNotFound(FLAT_NOT_FOUND)
        return flat

    async def house_of_flat(self, flat_id: FlatId) -> House:
        house = await self._houses.get_by_flat(flat_id)
        if house is None:
            raise EntityNotFound(FLAT_NOT_FOUND)
        return house
