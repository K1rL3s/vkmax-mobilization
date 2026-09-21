import itertools
from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta

from zheka.base import ZhekaType
from zheka.core.charges import previous_period, to_kopecks
from zheka.core.enums import (
    SERVICE_OF_METER,
    EventType,
    MeterType,
    RequestCategory,
    TariffZone,
)
from zheka.core.errors import EntityNotFound, InvalidRequest, InvalidState
from zheka.core.ids import FlatId, HouseId, MeterId, OrgId, UserId
from zheka.core.models import Meter, OrgSettings, Reading
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.meter_access import (
    FLAT_NOT_FOUND,
    MeterAccess,
    MeterCard,
    zones_of,
)
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.orgs import OrgsRepo

# сколько периодов назад предлагается житель за пределами окна подачи
PERIODS_BACK = 3
# скачок - расход минимум в 200% (2 раза) от медианы истории, никакого float
SPIKE_PERCENT = 200
# медиане нужно SPIKE_MIN_HISTORY прошлых расходов, а расход - это дельта
# между двумя показаниями, поэтому для порога нужно на одно показание больше
SPIKE_MIN_HISTORY = 3
# за сколько до конца поверки житель получает первое предупреждение
VERIFICATION_WARNING = timedelta(days=30)

# сколько прошлых показаний тянуть для истории и для расчета скачка
HISTORY_LIMIT = 50
_SPIKE_FETCH_LIMIT = 20
# house_average считается по всем показаниям периода разом, без постраничной
# отсечки - домов немного, а показание за период у каждого счетчика одно
_HOUSE_AVERAGE_LIMIT = 10_000

WRONG_ZONES = "Показания не соответствуют тарифным зонам счетчика"
PHOTO_REQUIRED = "Приложите фото показаний"
VERIFICATION_EXPIRED = "Срок поверки истек, начисление пойдет по нормативу"
PERIOD_NOT_ALLOWED = "Этот период недоступен для подачи показаний"
PERIOD_HAS_CHARGE = "За этот период уже выставлена квитанция"
WRONG_PERIOD = "Показания подаются за текущий период"
BELOW_PREVIOUS_WARNING = "Новое значение меньше предыдущего, уточните показание"

_ZONES_BY_COUNT: Mapping[int, frozenset[TariffZone]] = {
    1: frozenset({TariffZone.SINGLE}),
    2: frozenset({TariffZone.DAY, TariffZone.NIGHT}),
}


class PeriodOption(ZhekaType):
    period: date
    is_open: bool
    reason: str | None = None


class SubmitDraft(ZhekaType):
    period: date
    values: Mapping[TariffZone, int]
    photos: Sequence[str] = ()
    ocr_used: bool = False
    ocr_accepted: bool = False


class PeriodsData(ZhekaType):
    options: list[PeriodOption]
    submitted: set[date]


class ReadingRow(ZhekaType):
    reading: Reading
    meter: Meter
    values: dict[TariffZone, int]
    consumption: dict[TariffZone, int]
    amount: int | None


class SubmitResult(ZhekaType):
    row: ReadingRow
    house_average: int | None
    warning: str | None
    suggested_category: RequestCategory | None


def window_is_open(day: int, day_from: int, day_to: int, *, always_open: bool) -> bool:
    if always_open:
        return True
    if day_from <= day_to:
        return day_from <= day <= day_to
    return day >= day_from or day <= day_to


def current_period(today: date) -> date:
    return date(today.year, today.month, 1)


def _candidate_periods(today: date) -> list[date]:
    periods = [current_period(today)]
    while len(periods) < PERIODS_BACK:
        periods.append(previous_period(periods[-1]))
    return periods


def available_periods(
    today: date, closed_periods: Collection[date]
) -> list[PeriodOption]:
    return [
        PeriodOption(
            period=period,
            is_open=period not in closed_periods,
            reason=None if period not in closed_periods else PERIOD_HAS_CHARGE,
        )
        for period in _candidate_periods(today)
    ]


def consumption(
    values: Mapping[TariffZone, int],
    previous_values: Mapping[TariffZone, int] | None,
) -> dict[TariffZone, int]:
    # без предыдущего показания расход не посчитать: первая подача счетчика
    # не порождает начисление, а не мнимый расход от нуля
    if previous_values is None:
        return dict.fromkeys(values, 0)
    return {
        zone: value - previous_values.get(zone, value) for zone, value in values.items()
    }


def is_below_previous(
    values: Mapping[TariffZone, int],
    previous_values: Mapping[TariffZone, int] | None,
) -> bool:
    if previous_values is None:
        return False
    return any(
        value < previous_values.get(zone, value) for zone, value in values.items()
    )


def is_spike(current: int, history: Sequence[int]) -> bool:
    if len(history) < SPIKE_MIN_HISTORY:
        return False
    ordered = sorted(history)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        median = ordered[mid]
    else:
        median = (ordered[mid - 1] + ordered[mid]) // 2
    return current * 100 >= median * SPIKE_PERCENT


def _kopecks(consumption_map: Mapping[TariffZone, int], tariff_value: int) -> int:
    total = sum(value * tariff_value for value in consumption_map.values())
    return to_kopecks(total)


def _checked_values(meter: Meter, values: Mapping[TariffZone, int]) -> None:
    expected = _ZONES_BY_COUNT.get(meter.tariff_zones)
    if expected is None or set(values) != expected:
        raise InvalidRequest(WRONG_ZONES)


class ReadingsService:
    __slots__ = (
        "_access",
        "_charges",
        "_events",
        "_files",
        "_houses",
        "_meters",
        "_orgs",
    )

    def __init__(
        self,
        meters_repo: MetersRepo,
        charges_repo: ChargesRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        access: MeterAccess,
        files_service: FilesService,
        events_service: EventsService,
    ) -> None:
        self._meters = meters_repo
        self._charges = charges_repo
        self._houses = houses_repo
        self._orgs = orgs_repo
        self._access = access
        self._files = files_service
        self._events = events_service

    async def list_meters(self, flat_id: FlatId) -> list[MeterCard]:
        meters = await self._meters.list_for_flat(flat_id)
        today = datetime.now(UTC).date()
        return [await self._access.meter_card(meter, today) for meter in meters]

    async def periods(self, flat_id: FlatId) -> PeriodsData:
        house_id = await self._house_id_of_flat(flat_id)
        today = datetime.now(UTC).date()

        settings = await self._window_settings(house_id)
        if window_accepts(today, settings):
            options = [
                PeriodOption(period=window_period(today, settings), is_open=True)
            ]
        else:
            closed = {
                period
                for period in _candidate_periods(today)
                if await self._charges.get_by_period(flat_id, period) is not None
            }
            options = available_periods(today, closed)

        submitted = await self._submitted_periods(
            flat_id,
            {option.period for option in options},
        )
        return PeriodsData(options=options, submitted=submitted)

    async def history(self, user_id: UserId, meter_id: MeterId) -> list[ReadingRow]:
        meter = await self._access.get_meter(meter_id)
        resident = await self._access.verified_resident(user_id, FlatId(meter.flat_id))
        house_id = await self._house_id_of_flat(FlatId(meter.flat_id))
        readings = await self._meters.list_readings(meter_id, HISTORY_LIMIT)

        previous_cache: dict[date, Reading | None] = {}
        tariff_cache: dict[date, int | None] = {}
        rows = []
        for reading in readings:
            if reading.period not in previous_cache:
                previous_cache[reading.period] = await self._meters.previous_reading(
                    meter_id,
                    reading.period,
                )
            previous = previous_cache[reading.period]
            previous_values = None if previous is None else zones_of(previous.values)
            values_map = zones_of(reading.values)
            consumption_map = consumption(values_map, previous_values)

            amount = None
            if resident.can_see_charges:
                if reading.period not in tariff_cache:
                    tariff = await self._charges.tariff_at(
                        house_id,
                        SERVICE_OF_METER[meter.type],
                        reading.period,
                    )
                    tariff_cache[reading.period] = (
                        None if tariff is None else tariff.value
                    )
                tariff_value = tariff_cache[reading.period]
                if tariff_value is not None:
                    amount = _kopecks(consumption_map, tariff_value)

            rows.append(
                ReadingRow(
                    reading=reading,
                    meter=meter,
                    values=values_map,
                    consumption=consumption_map,
                    amount=amount,
                ),
            )
        return rows

    async def submit(
        self,
        user_id: UserId,
        meter_id: MeterId,
        draft: SubmitDraft,
    ) -> SubmitResult:
        meter = await self._access.get_meter(meter_id)
        resident = await self._access.verified_resident(user_id, FlatId(meter.flat_id))
        flat_id = FlatId(meter.flat_id)
        house_id = await self._house_id_of_flat(flat_id)

        _checked_values(meter, draft.values)
        if not draft.photos:
            raise InvalidRequest(PHOTO_REQUIRED)
        for name in draft.photos:
            self._files.path_of(name)

        now = datetime.now(UTC)
        today = now.date()

        if (
            meter.next_verification_date is not None
            and meter.next_verification_date < today
        ):
            raise InvalidState(VERIFICATION_EXPIRED)

        settings = await self._window_settings(house_id)
        out_of_window = not window_accepts(today, settings)
        if out_of_window:
            if draft.period not in _candidate_periods(today):
                raise InvalidState(PERIOD_NOT_ALLOWED)
            charge = await self._charges.get_by_period(flat_id, draft.period)
            if charge is not None:
                raise InvalidState(PERIOD_HAS_CHARGE)
        elif draft.period != window_period(today, settings):
            raise InvalidState(WRONG_PERIOD)

        previous = await self._meters.previous_reading(meter_id, draft.period)
        previous_values = None if previous is None else zones_of(previous.values)
        below = is_below_previous(draft.values, previous_values)
        consumption_map = consumption(draft.values, previous_values)

        reading = await self._meters.add_reading(
            meter_id,
            draft.period,
            draft.values,
            draft.photos,
            ocr_used=draft.ocr_used,
            ocr_accepted=draft.ocr_accepted,
            is_below_previous=below,
            submitted_at=now,
            submitted_by=user_id,
        )

        tariff = await self._charges.tariff_at(
            house_id, SERVICE_OF_METER[meter.type], draft.period
        )
        amount = None
        if tariff is not None and resident.can_see_charges:
            amount = _kopecks(consumption_map, tariff.value)

        house_average = await self.house_average(house_id, meter.type, draft.period)

        history = await self._spike_history(meter_id, draft.period)
        spike = is_spike(sum(consumption_map.values()), history)

        await self._events.record(
            EventType.READING_SUBMITTED,
            user_id=user_id,
            meter_type=meter.type.value,
            ocr_used=draft.ocr_used,
            ocr_accepted=draft.ocr_accepted,
            is_below_previous=below,
            out_of_window=out_of_window,
        )

        row = ReadingRow(
            reading=reading,
            meter=meter,
            values=dict(draft.values),
            consumption=consumption_map,
            amount=amount,
        )
        return SubmitResult(
            row=row,
            house_average=house_average,
            warning=BELOW_PREVIOUS_WARNING if below else None,
            suggested_category=RequestCategory.LEAK if spike else None,
        )

    async def _submitted_periods(
        self,
        flat_id: FlatId,
        periods: Collection[date],
    ) -> set[date]:
        meters = await self._meters.list_for_flat(flat_id)
        submitted: set[date] = set()
        for period in periods:
            for meter in meters:
                reading = await self._meters.latest_reading(MeterId(meter.id), period)
                if reading is not None:
                    submitted.add(period)
                    break
        return submitted

    async def _window_settings(self, house_id: HouseId) -> OrgSettings | None:
        house = await self._houses.get(house_id)
        if house is None or house.org_id is None:
            return None
        return await self._orgs.get_settings(OrgId(house.org_id))

    async def house_average(
        self,
        house_id: HouseId,
        meter_type: MeterType,
        period: date,
    ) -> int | None:
        readings, _total = await self._meters.list_house_readings(
            house_id,
            period=period,
            meter_type=meter_type,
            limit=_HOUSE_AVERAGE_LIMIT,
        )
        # первое по meter_id и есть самое свежее: readings отсортированы по
        # submitted_at по убыванию, а повторная подача чинит именно значение
        latest_by_meter: dict[MeterId, Reading] = {}
        for reading in readings:
            latest_by_meter.setdefault(MeterId(reading.meter_id), reading)

        totals: list[int] = []
        for meter_id, reading in latest_by_meter.items():
            previous = await self._meters.previous_reading(meter_id, period)
            previous_values = None if previous is None else zones_of(previous.values)
            delta = consumption(zones_of(reading.values), previous_values)
            totals.append(sum(delta.values()))

        if not totals:
            return None
        return sum(totals) // len(totals)

    async def _spike_history(self, meter_id: MeterId, period: date) -> list[int]:
        readings = await self._meters.list_readings(meter_id, _SPIKE_FETCH_LIMIT)
        by_period: dict[date, Reading] = {}
        for reading in readings:
            if reading.period >= period:
                continue
            # первое увиденное на период и есть самое свежее (submitted_at desc)
            by_period.setdefault(reading.period, reading)
        ordered = sorted(by_period.values(), key=lambda reading: reading.period)

        totals: list[int] = []
        for earlier, later in itertools.pairwise(ordered):
            delta = consumption(zones_of(later.values), zones_of(earlier.values))
            totals.append(sum(delta.values()))
        return totals

    async def _house_id_of_flat(self, flat_id: FlatId) -> HouseId:
        flat = await self._houses.get_flat(flat_id)
        if flat is None:
            raise EntityNotFound(FLAT_NOT_FOUND)
        return HouseId(flat.house_id)


def window_accepts(today: date, settings: OrgSettings | None) -> bool:
    # без организации или без строки настроек окно открыто всегда
    if settings is None:
        return True
    return window_is_open(
        today.day,
        settings.meter_window_day_from,
        settings.meter_window_day_to,
        always_open=settings.meter_window_always_open,
    )


def window_period(today: date, settings: OrgSettings | None) -> date:
    # окно через конец месяца - один период, месяц его открытия: показание,
    # поданное 3-го в окно 25-5, относится к тому же месяцу, что и поданное 27-го
    if (
        settings is not None
        and not settings.meter_window_always_open
        and settings.meter_window_day_from > settings.meter_window_day_to
        and today.day <= settings.meter_window_day_to
    ):
        return previous_period(today)
    return current_period(today)
