from datetime import date

from zheka.base import ZhekaType
from zheka.core.enums import MeterType, TariffZone
from zheka.core.errors import EntityNotFound
from zheka.core.ids import HouseId, MeterId, OrgId
from zheka.core.models import Meter, Reading, User
from zheka.core.services.meter_access import zones_of
from zheka.core.services.readings import consumption
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.users import UsersRepo


class AdminReadingRow(ZhekaType):
    reading: Reading
    meter: Meter
    flat_number: str
    values: dict[TariffZone, int]
    consumption: dict[TariffZone, int]
    submitted_by: User


class AdminReadingsService:
    __slots__ = ("_houses", "_meters", "_users")

    def __init__(
        self, meters_repo: MetersRepo, houses_repo: HousesRepo, users_repo: UsersRepo
    ) -> None:
        self._meters = meters_repo
        self._houses = houses_repo
        self._users = users_repo

    async def admin_list(
        self,
        org_id: OrgId,
        house_id: HouseId,
        period: date | None,
        meter_type: MeterType | None,
        *,
        only_below_previous: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminReadingRow], int]:
        house = await self._houses.get_for_org(house_id, org_id)
        if house is None:
            raise EntityNotFound("Дом не найден")

        readings, total = await self._meters.list_house_readings(
            house_id,
            period=period,
            meter_type=meter_type,
            only_below_previous=only_below_previous,
            limit=limit,
            offset=offset,
        )
        meters = {
            meter.id: meter
            for meter in await self._meters.list_by_ids(
                {reading.meter_id for reading in readings}
            )
        }
        flats = {
            flat.id: flat
            for flat in await self._houses.list_flats_by_ids(
                {meter.flat_id for meter in meters.values()}
            )
        }
        users = {
            user.id: user
            for user in await self._users.list_by_ids(
                {reading.submitted_by for reading in readings}
            )
        }

        previous_cache: dict[tuple[MeterId, date], Reading | None] = {}
        rows = []
        for reading in readings:
            meter = meters[reading.meter_id]
            key = (reading.meter_id, reading.period)
            if key not in previous_cache:
                previous_cache[key] = await self._meters.previous_reading(*key)
            previous = previous_cache[key]
            previous_values = None if previous is None else zones_of(previous.values)
            values_map = zones_of(reading.values)
            rows.append(
                AdminReadingRow(
                    reading=reading,
                    meter=meter,
                    flat_number=flats[meter.flat_id].number,
                    values=values_map,
                    consumption=consumption(values_map, previous_values),
                    submitted_by=users[reading.submitted_by],
                )
            )
        return rows, total
