from collections.abc import Sequence
from datetime import UTC, date, datetime

from zheka.base import ZhekaType
from zheka.core.charges import (
    ChargeLine,
    LineDelta,
    breakdown as compute_breakdown,
    parse_lines,
    previous_period,
)
from zheka.core.enums import (
    SERVICE_LABELS,
    SERVICE_OF_METER,
    EventType,
    RequestCategory,
    RequestChannel,
    ServiceType,
)
from zheka.core.errors import EntityNotFound, InvalidState, NotEnoughRights
from zheka.core.ids import ChargeId, FlatId, HouseId, MeterId, RequestId, UserId
from zheka.core.models import Charge, Flat, House, Resident, Tariff
from zheka.core.services.events import EventsService
from zheka.core.services.meter_access import MeterAccess
from zheka.core.services.readings import ReadingsService
from zheka.core.services.requests import RequestDraft, RequestsService
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.meters import MetersRepo

FLAT_NOT_FOUND = "Квартира не найдена"
CHARGE_NOT_FOUND = "Квитанция не найдена"
NOT_VERIFIED = "Подтвердите квартиру, чтобы видеть начисления"
CANNOT_SEE_CHARGES = "Начисления недоступны для вашей роли"
ALREADY_PAID = "Квитанция уже оплачена"

# сколько последних периодов расхода показывать рядом с разбором начисления
CONSUMPTION_POINTS = 6


class ConsumptionPoint(ZhekaType):
    period: date
    consumption: int  # тысячные единицы измерения


class ServiceConsumption(ZhekaType):
    service: ServiceType
    meter_id: MeterId
    points: list[ConsumptionPoint]
    house_average: int | None  # тысячные единицы измерения


class ChargeCardData(ZhekaType):
    charge: Charge
    house: House
    flat: Flat
    lines: list[ChargeLine]


class BreakdownLine(ZhekaType):
    delta: LineDelta
    current: ChargeLine | None
    previous: ChargeLine | None


class BreakdownData(ZhekaType):
    charge: Charge
    previous_charge: Charge | None
    delta: int
    lines: list[BreakdownLine]
    consumption: list[ServiceConsumption]


class PaymentResult(ZhekaType):
    charge_id: ChargeId
    paid_at: datetime


def _rubles(kopecks: int) -> str:
    sign = "-" if kopecks < 0 else "+"
    whole, cents = divmod(abs(kopecks), 100)
    return f"{sign}{whole}.{cents:02d}"


def _dispute_description(
    charge: Charge,
    lines: Sequence[LineDelta],
    total_delta: int,
    comment: str,
    service: ServiceType | None,
) -> str:
    period_text = charge.period.strftime("%m.%Y")
    if service is not None:
        line = next((item for item in lines if item.service is service), None)
        if line is None:
            summary = f"По строке «{SERVICE_LABELS[service]}» за {period_text}."
        else:
            summary = (
                f"По строке «{SERVICE_LABELS[service]}» за {period_text}: "
                f"{_rubles(line.delta)} руб."
            )
    else:
        top = ", ".join(
            f"{SERVICE_LABELS[item.service]} {_rubles(item.delta)} руб"
            for item in lines[:3]
        )
        summary = (
            f"Начисление за {period_text} изменилось на {_rubles(total_delta)} руб."
        )
        if top:
            summary = f"{summary} {top}."
    return f"{summary}\n\n{comment.strip()}"


class ChargesService:
    __slots__ = (
        "_access",
        "_charges",
        "_events",
        "_houses",
        "_meters",
        "_readings",
        "_requests",
    )

    def __init__(
        self,
        charges_repo: ChargesRepo,
        meters_repo: MetersRepo,
        houses_repo: HousesRepo,
        access: MeterAccess,
        readings_service: ReadingsService,
        requests_service: RequestsService,
        events_service: EventsService,
    ) -> None:
        self._charges = charges_repo
        self._meters = meters_repo
        self._houses = houses_repo
        self._access = access
        self._readings = readings_service
        self._requests = requests_service
        self._events = events_service

    async def tariffs(self, house_id: HouseId) -> Sequence[Tariff]:
        return await self._charges.list_tariffs(house_id)

    async def list_for_flat(
        self,
        flat_id: FlatId,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Charge], int]:
        return await self._charges.list_for_flat(flat_id, limit, offset)

    async def card(self, charge_id: ChargeId, user_id: UserId) -> ChargeCardData:
        charge, _resident = await self._verified_charge(charge_id, user_id)
        flat = await self._get_flat(FlatId(charge.flat_id))
        house = await self._houses.get(HouseId(flat.house_id))
        if house is None:
            raise EntityNotFound(FLAT_NOT_FOUND)
        return ChargeCardData(
            charge=charge,
            house=house,
            flat=flat,
            lines=parse_lines(charge.lines),
        )

    async def breakdown(self, charge_id: ChargeId, user_id: UserId) -> BreakdownData:
        charge, _resident = await self._verified_charge(charge_id, user_id)
        flat_id = FlatId(charge.flat_id)
        house_id = await self._house_id_of_flat(flat_id)

        current_lines, previous_lines, previous_charge = await self._diffed_lines(
            charge
        )
        core = compute_breakdown(current_lines, previous_lines)

        current_by_service = {line.service: line for line in current_lines}
        previous_by_service = {line.service: line for line in previous_lines}
        lines = [
            BreakdownLine(
                delta=delta,
                current=current_by_service.get(delta.service),
                previous=previous_by_service.get(delta.service),
            )
            for delta in core.lines
        ]

        consumption = await self._consumption(user_id, flat_id, house_id, charge.period)

        await self._events.record(
            EventType.CHARGE_BREAKDOWN_OPENED,
            user_id=user_id,
            charge_id=charge_id,
        )
        return BreakdownData(
            charge=charge,
            previous_charge=previous_charge,
            delta=core.delta,
            lines=lines,
            consumption=consumption,
        )

    async def dispute(
        self,
        charge_id: ChargeId,
        user_id: UserId,
        comment: str,
        service: ServiceType | None,
    ) -> RequestId:
        charge, _resident = await self._verified_charge(charge_id, user_id)
        flat_id = FlatId(charge.flat_id)
        house_id = await self._house_id_of_flat(flat_id)

        current_lines, previous_lines, _previous_charge = await self._diffed_lines(
            charge
        )
        core = compute_breakdown(current_lines, previous_lines)
        description = _dispute_description(
            charge,
            core.lines,
            core.delta,
            comment,
            service,
        )
        photos = await self._period_photos(flat_id, charge.period)

        card = await self._requests.create(
            user_id,
            house_id,
            RequestDraft(
                category=RequestCategory.CHARGE_DISPUTE,
                description=description,
                flat_id=flat_id,
                photos=photos,
            ),
            channel=RequestChannel.MINIAPP,
        )
        request_id = RequestId(card.request.id)
        await self._events.record(
            EventType.CHARGE_DISPUTED,
            user_id=user_id,
            charge_id=charge_id,
            request_id=request_id,
        )
        return request_id

    async def pay_demo(self, charge_id: ChargeId, user_id: UserId) -> PaymentResult:
        charge, _resident = await self._verified_charge(charge_id, user_id)
        if charge.paid_at is not None:
            raise InvalidState(ALREADY_PAID)
        paid_at = datetime.now(UTC)
        await self._charges.mark_paid(charge, paid_at)
        return PaymentResult(charge_id=ChargeId(charge.id), paid_at=paid_at)

    async def _verified_charge(
        self,
        charge_id: ChargeId,
        user_id: UserId,
    ) -> tuple[Charge, Resident]:
        charge = await self._charges.get(charge_id)
        if charge is None:
            raise EntityNotFound(CHARGE_NOT_FOUND)
        resident = await self._access.verified_resident(user_id, FlatId(charge.flat_id))
        if not resident.can_see_charges:
            raise NotEnoughRights(CANNOT_SEE_CHARGES)
        return charge, resident

    async def _diffed_lines(
        self,
        charge: Charge,
    ) -> tuple[list[ChargeLine], list[ChargeLine], Charge | None]:
        # общий первый шаг разбора и оспаривания - строки текущей квитанции
        # и квитанции месяцем раньше, если она есть
        current_lines = parse_lines(charge.lines)
        previous_charge = await self._charges.get_by_period(
            FlatId(charge.flat_id),
            previous_period(charge.period),
        )
        previous_lines = (
            [] if previous_charge is None else parse_lines(previous_charge.lines)
        )
        return current_lines, previous_lines, previous_charge

    async def _get_flat(self, flat_id: FlatId) -> Flat:
        flat = await self._houses.get_flat(flat_id)
        if flat is None:
            raise EntityNotFound(FLAT_NOT_FOUND)
        return flat

    async def _house_id_of_flat(self, flat_id: FlatId) -> HouseId:
        flat = await self._get_flat(flat_id)
        return HouseId(flat.house_id)

    async def _period_photos(self, flat_id: FlatId, period: date) -> list[str]:
        meters = await self._meters.list_for_flat(flat_id)
        photos: list[str] = []
        for meter in meters:
            reading = await self._meters.latest_reading(MeterId(meter.id), period)
            if reading is not None:
                photos.extend(reading.photo_paths)
        return photos

    async def _consumption(
        self,
        user_id: UserId,
        flat_id: FlatId,
        house_id: HouseId,
        period: date,
    ) -> list[ServiceConsumption]:
        meters = await self._meters.list_for_flat(flat_id)
        result: list[ServiceConsumption] = []
        for meter in meters:
            history = await self._readings.history(user_id, MeterId(meter.id))
            by_period: dict[date, int] = {}
            for row in history.rows:
                if row.reading.period > period:
                    continue
                # первая встреченная строка на период и есть самая свежая
                # подача - history() возвращает показания по submitted_at desc
                by_period.setdefault(row.reading.period, sum(row.consumption.values()))
            recent_periods = sorted(by_period)[-CONSUMPTION_POINTS:]
            points = [
                ConsumptionPoint(period=recent, consumption=by_period[recent])
                for recent in recent_periods
            ]
            house_average = await self._readings.house_average(
                house_id,
                meter.type,
                period,
            )
            result.append(
                ServiceConsumption(
                    service=SERVICE_OF_METER[meter.type],
                    meter_id=MeterId(meter.id),
                    points=points,
                    house_average=house_average,
                ),
            )
        return result
