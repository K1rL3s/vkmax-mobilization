import dataclasses
from datetime import UTC, date, datetime, time, timedelta
from random import Random

from zheka.base import ZhekaType
from zheka.core.charges import ChargeLine, previous_period, to_kopecks
from zheka.core.enums import (
    SERVICE_OF_METER,
    MeterType,
    OrgRole,
    ResidentRole,
    ServiceType,
    TariffZone,
)
from zheka.core.errors import EntityNotFound, NotEnoughRights
from zheka.core.ids import UserId
from zheka.core.models import Flat, Organization
from zheka.core.services.houses import CONSENT_REQUIRED, ResidencyView
from zheka.core.services.profile import OrgMembershipView
from zheka.core.services.readings import current_period
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

DEMO_INNS = ("9900000001", "9900000010", "9900000020", "9900000030", "9900000040")
DEMO_INN = DEMO_INNS[0]
NOT_SEEDED = "Демо-доступ еще не готов: демо-данные не загружены"

CHARGED_MONTHS = 6
VERIFICATION_SOON = timedelta(days=21)

_MONTHLY: dict[MeterType, dict[TariffZone, int]] = {
    MeterType.COLD_WATER: {TariffZone.SINGLE: 7_000},
    MeterType.HOT_WATER: {TariffZone.SINGLE: 4_500},
    MeterType.ELECTRICITY: {TariffZone.DAY: 160_000, TariffZone.NIGHT: 70_000},
}
_SERIAL_CODES = {
    MeterType.COLD_WATER: "ХВ",
    MeterType.HOT_WATER: "ГВ",
    MeterType.ELECTRICITY: "ЭЭ",
}
_AREA_SERVICES = (ServiceType.MAINTENANCE, ServiceType.OVERHAUL)
SPIKE_FACTOR = 3
BELOW_NOTE = "Показание меньше предыдущего, объем к проверке"


class DemoAccess(ZhekaType):
    membership: OrgMembershipView
    residency: ResidencyView


def demo_flat_number(user_id: UserId) -> str:
    return f"Д{user_id}"


class DemoService:
    __slots__ = ("_charges", "_houses", "_meters", "_orgs", "_residents", "_users")

    def __init__(
        self,
        orgs_repo: OrgsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        meters_repo: MetersRepo,
        charges_repo: ChargesRepo,
        users_repo: UsersRepo,
    ) -> None:
        self._orgs = orgs_repo
        self._houses = houses_repo
        self._residents = residents_repo
        self._meters = meters_repo
        self._charges = charges_repo
        self._users = users_repo

    async def activate(
        self,
        user_id: UserId,
        number: int = 1,
        role: OrgRole = OrgRole.EMPLOYEE,
    ) -> DemoAccess:
        org, residency = await self.settle(user_id, number)
        member = await self._orgs.add_member_or_get(org.id, user_id, role)
        if role is OrgRole.ADMIN:
            await self._orgs.set_member_role(member, role)
        return DemoAccess(
            membership=OrgMembershipView(member=member, org=org),
            residency=residency,
        )

    async def furnish(
        self,
        flat: Flat,
        owner_id: UserId,
        today: date,
        *,
        spike: bool = False,
        below: bool = False,
        verification_soon: bool = False,
    ) -> None:
        rng = Random(f"flat:{flat.house_id}:{flat.number}")
        months = [current_period(today)]
        for _ in range(CHARGED_MONTHS + 1):
            months.insert(0, previous_period(months[0]))
        periods = months[:-1]

        usage: dict[MeterType, list[dict[TariffZone, int]]] = {}
        for meter_type, monthly in _MONTHLY.items():
            soon = verification_soon and meter_type is MeterType.HOT_WATER
            meter = await self._meters.add(
                flat.id,
                meter_type,
                len(monthly),
                f"ДЕМО-{_SERIAL_CODES[meter_type]}-{flat.id:06d}",
                (
                    today + VERIFICATION_SOON
                    if soon
                    else date(today.year + rng.randint(2, 6), today.month, 1)
                ),
            )
            if meter is None:
                continue
            values = {
                zone: base * rng.randint(20, 60) for zone, base in monthly.items()
            }
            used_by_period: list[dict[TariffZone, int]] = []
            for index, period in enumerate(periods):
                last = index == len(periods) - 1
                used = {
                    zone: base * rng.randint(80, 120) // 100
                    for zone, base in monthly.items()
                }
                if index == 0:
                    used = dict.fromkeys(monthly, 0)
                elif last and spike and meter_type is MeterType.COLD_WATER:
                    used = {zone: base * SPIKE_FACTOR for zone, base in monthly.items()}
                elif last and below and meter_type is MeterType.HOT_WATER:
                    used = {zone: -rng.randint(500, 1_500) for zone in monthly}
                values = {zone: values[zone] + used[zone] for zone in values}
                used_by_period.append(used)
                await self._meters.add_reading(
                    meter.id,
                    period,
                    values,
                    [],
                    ocr_used=False,
                    ocr_accepted=False,
                    is_below_previous=any(value < 0 for value in used.values()),
                    submitted_at=datetime.combine(
                        period.replace(day=rng.randint(15, 25)),
                        time(rng.randint(8, 21), rng.randint(0, 59)),
                        UTC,
                    ),
                    submitted_by=owner_id,
                )
            usage[meter_type] = used_by_period

        for index, period in enumerate(periods[1:], start=1):
            lines = await self._lines(
                flat,
                period,
                {meter_type: used[index] for meter_type, used in usage.items()},
            )
            issued = datetime.combine(months[index + 1], time(6), UTC)
            paid_at = (
                None
                if index == len(periods) - 1
                else issued + timedelta(days=rng.randint(2, 20))
            )
            await self._charges.add(
                flat.id,
                period,
                [dataclasses.asdict(line) for line in lines],
                sum(line.amount for line in lines),
                issued,
                paid_at,
            )

    async def _lines(
        self,
        flat: Flat,
        period: date,
        used: dict[MeterType, dict[TariffZone, int]],
    ) -> list[ChargeLine]:
        house_id = flat.house_id
        lines = []
        for meter_type, zones in used.items():
            service = SERVICE_OF_METER[meter_type]
            tariff = await self._charges.tariff_at(house_id, service, period)
            if tariff is None:
                continue
            below = any(value < 0 for value in zones.values())
            volumes = {zone: max(value, 0) for zone, value in zones.items()}
            lines.append(
                ChargeLine(
                    service=service,
                    amount=to_kopecks(
                        sum(volume * tariff.value for volume in volumes.values()),
                    ),
                    volume=sum(volumes.values()),
                    tariff=tariff.value,
                    unit=tariff.unit,
                    note=BELOW_NOTE if below else None,
                ),
            )
        if flat.area is None:
            return lines
        for service in _AREA_SERVICES:
            tariff = await self._charges.tariff_at(house_id, service, period)
            if tariff is None:
                continue
            lines.append(
                ChargeLine(
                    service=service,
                    amount=to_kopecks(flat.area * tariff.value, is_area=True),
                    tariff=tariff.value,
                    unit=tariff.unit,
                    note=f"Площадь {flat.area // 100},{flat.area % 100:02d} м²",
                ),
            )
        return lines

    async def join(
        self,
        user_id: UserId,
        number: int,
        role: OrgRole,
    ) -> OrgMembershipView:
        org = await self._org(user_id, number)
        member = await self._orgs.add_member_or_get(org.id, user_id, role)
        await self._orgs.set_member_role(member, role)
        return OrgMembershipView(member=member, org=org)

    async def settle(
        self,
        user_id: UserId,
        number: int,
    ) -> tuple[Organization, ResidencyView]:
        org = await self._org(user_id, number)
        houses = await self._houses.list_for_org(org.id)
        if not houses:
            raise EntityNotFound(NOT_SEEDED)
        house = houses[0]
        house_id = house.id

        now = datetime.now(UTC)
        flat_number = demo_flat_number(user_id)
        flat, created = await self._houses.add_flat_or_get(
            house_id,
            flat_number,
            area=Random(f"demo-flat:{user_id}").randint(3_800, 7_800),
            account_no=demo_account_no(flat_number),
        )
        if created:
            await self.furnish(
                flat,
                user_id,
                house.local(now).date(),
                verification_soon=True,
            )

        resident, _created = await self._residents.add_or_get(
            user_id,
            house_id,
            flat.id,
            None,
            ResidentRole.OWNER,
        )
        if resident.verified_at is None:
            await self._residents.set_verified(resident, flat.id, now, None)
        return org, ResidencyView(
            resident=resident,
            house=house,
            flat=flat,
            is_connected=True,
        )

    async def _org(self, user_id: UserId, number: int) -> Organization:
        user = await self._users.get_by_id(user_id)
        if user is None or user.consent_at is None:
            raise NotEnoughRights(CONSENT_REQUIRED)
        org = await self._orgs.get_by_inn(DEMO_INNS[number - 1])
        if org is None:
            raise EntityNotFound(NOT_SEEDED)
        return org


def demo_account_no(flat_number: str) -> str:
    return flat_number.zfill(10)
