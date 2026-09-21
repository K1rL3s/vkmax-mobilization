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
from zheka.core.ids import FlatId, HouseId, MeterId, OrgId, UserId
from zheka.core.models import Flat
from zheka.core.services.houses import CONSENT_REQUIRED, ResidencyView
from zheka.core.services.profile import OrgMembershipView
from zheka.core.services.readings import current_period
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

# ИНН демо-организации не проходит контрольную сумму: такого ИНН нет ни у
# одной настоящей организации, и он не столкнется ни с реестром, ни с
# настоящей регистрацией
DEMO_INN = "9900000001"
NOT_SEEDED = "Демо-доступ еще не готов: демо-данные не загружены"

# сколько закрытых периодов у квартиры: первое показание - точка отсчета, по
# нему нет расхода, поэтому показаний на одно больше, чем квитанций
CHARGED_MONTHS = 6
VERIFICATION_SOON = timedelta(days=21)

# расход в месяц, тысячные единицы: вода в кубометрах, свет в кВт·ч по зонам
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
    # номер от пользователя: два проверяющих в одну секунду не спорят за
    # следующий свободный номер, и блокировка не нужна
    return f"Д{user_id}"


def _line_json(line: ChargeLine) -> dict[str, object]:
    return dataclasses.asdict(line)


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

    async def activate(self, user_id: UserId) -> DemoAccess:
        # обе ссылки дают обе роли: один аккаунт видит продукт целиком.
        # Согласие проверяется и здесь, как в HousesService.link: маршрут и
        # бот до сервиса без него не пускают, но житель заводится не через link
        user = await self._users.get_by_id(user_id)
        if user is None or user.consent_at is None:
            raise NotEnoughRights(CONSENT_REQUIRED)
        org = await self._orgs.get_by_inn(DEMO_INN)
        if org is None:
            raise EntityNotFound(NOT_SEEDED)
        # у демо-организации ровно один дом - демо-дом, так его кладет сид
        houses = await self._houses.list_for_org(OrgId(org.id))
        if not houses:
            raise EntityNotFound(NOT_SEEDED)
        house = houses[0]
        house_id = HouseId(house.id)

        member = await self._orgs.add_member_or_get(
            OrgId(org.id),
            user_id,
            OrgRole.EMPLOYEE,
        )
        now = datetime.now(UTC)
        rng = Random(f"demo-flat:{user_id}")
        flat, created = await self._houses.add_flat_or_get(
            house_id,
            demo_flat_number(user_id),
            area=rng.randint(3_800, 7_800),
            # номер квартиры с буквой: у засеянных квартир номера из цифр, и
            # лицевые счета не совпадут
            account_no=f"ДЕМО-{house_id}-{demo_flat_number(user_id)}",
        )
        if created:
            # чистая история без скачка: первое свое показание проверяющий
            # сравнивает со спокойным фоном
            await self.furnish(flat, user_id, now.date(), verification_soon=True)

        resident, _created = await self._residents.add_or_get(
            user_id,
            house_id,
            FlatId(flat.id),
            None,
            ResidentRole.OWNER,
        )
        if resident.verified_at is None:
            await self._residents.set_verified(resident, FlatId(flat.id), now, None)
        return DemoAccess(
            membership=OrgMembershipView(member=member, org=org),
            residency=ResidencyView(
                resident=resident,
                house=house,
                flat=flat,
                is_connected=True,
            ),
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
        # счетчики, показания и квитанции квартиры за полгода до today.
        # Текущий период остается открытым: подать его - то, ради чего
        # проверяющий пришел
        rng = Random(f"flat:{flat.house_id}:{flat.number}")
        periods = [current_period(today)]
        for _ in range(CHARGED_MONTHS + 1):
            periods.insert(0, previous_period(periods[0]))
        periods.pop()

        # по счетчику: показания по периодам и расход по периодам
        usage: dict[MeterType, list[dict[TariffZone, int]]] = {}
        for meter_type, monthly in _MONTHLY.items():
            meter = await self._meters.add(
                FlatId(flat.id),
                meter_type,
                len(monthly),
                f"ДЕМО-{_SERIAL_CODES[meter_type]}-{flat.id:06d}",
                self._verification_date(
                    meter_type,
                    today,
                    rng,
                    soon=verification_soon,
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
                    MeterId(meter.id),
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
            issued = datetime.combine(
                periods[index + 1]
                if index + 1 < len(periods)
                else current_period(today),
                time(6),
                UTC,
            )
            # оплачены все, кроме последней: демо-оплате есть что оплатить
            paid_at = (
                None
                if index == len(periods) - 1
                else issued + timedelta(days=rng.randint(2, 20))
            )
            await self._charges.add(
                FlatId(flat.id),
                period,
                [_line_json(line) for line in lines],
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
        house_id = HouseId(flat.house_id)
        lines = []
        for meter_type, zones in used.items():
            service = SERVICE_OF_METER[meter_type]
            tariff = await self._charges.tariff_at(house_id, service, period)
            if tariff is None:
                continue
            below = any(value < 0 for value in zones.values())
            # начисление по показанию меньше предыдущего не выставляется в
            # минус: объем ноль, пока УК его не проверит
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

    def _verification_date(
        self,
        meter_type: MeterType,
        today: date,
        rng: Random,
        *,
        soon: bool,
    ) -> date:
        # горячая вода с поверкой через три недели - ровно сценарий
        # предупреждения бота
        if soon and meter_type is MeterType.HOT_WATER:
            return today + VERIFICATION_SOON
        return date(today.year + rng.randint(2, 6), today.month, 1)
