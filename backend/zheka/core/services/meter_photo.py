from collections.abc import Mapping, Sequence
from datetime import date

from zheka.base import ZhekaType
from zheka.core.enums import (
    SERVICE_LABELS,
    SERVICE_OF_METER,
    MeterType,
    ResidentStatus,
    TariffZone,
)
from zheka.core.errors import InvalidRequest
from zheka.core.ids import FlatId, MeterId, UserId
from zheka.core.services.meter_access import MeterCard
from zheka.core.services.profile import ProfileService
from zheka.core.services.readings import ReadingsService, SubmitDraft, SubmitResult

NO_HOUSE = "🏠 Сначала найдите свой дом, тогда будет куда передать показания"
NOT_CONNECTED = "😔 УК этого дома еще не подключена, показания передать некому"
NOT_VERIFIED = "🔐 Показания принимаются от подтвержденной квартиры"
NO_METERS = "📟 У квартиры нет счетчиков, которые можно подать фото"
TWO_TARIFF = "📱 Двухтарифный счетчик передайте в приложении"
WINDOW_CLOSED = "📅 Прием показаний сейчас закрыт"
UNKNOWN_METER = "Этот счетчик нельзя подать фото"

METER_EMOJI: Mapping[MeterType, str] = {
    MeterType.COLD_WATER: "💧",
    MeterType.HOT_WATER: "🛁",
    MeterType.ELECTRICITY: "⚡",
    MeterType.GAS: "🔥",
    MeterType.HEATING: "🌞",
}
METER_UNIT: Mapping[MeterType, str] = {
    MeterType.COLD_WATER: "м³",
    MeterType.HOT_WATER: "м³",
    MeterType.ELECTRICITY: "кВт·ч",
    MeterType.GAS: "м³",
    MeterType.HEATING: "Гкал",
}
TYPICAL_MONTH: Mapping[MeterType, int] = {
    MeterType.COLD_WATER: 5,
    MeterType.HOT_WATER: 3,
    MeterType.ELECTRICITY: 200,
    MeterType.GAS: 15,
    MeterType.HEATING: 1,
}
MONTHLY_LIMIT_FACTOR = 10
MILLI = 1000
DIGITS = 3


class PhotoMeters(ZhekaType):
    flat_id: FlatId | None = None
    period: date | None = None
    cards: Sequence[MeterCard] = ()
    refusal: str | None = None


def meter_label(card: MeterCard) -> str:
    meter = card.meter
    service = SERVICE_LABELS[SERVICE_OF_METER[meter.type]]
    return f"{METER_EMOJI[meter.type]} {service} №{meter.serial}"


def format_volume(milli: int) -> str:
    sign = "-" if milli < 0 else ""
    whole, part = divmod(abs(milli), MILLI)
    return f"{sign}{whole},{part:03d}"


def parse_volume(text: str) -> int | None:
    normalized = "".join(text.split()).replace(",", ".")
    whole, dot, part = normalized.partition(".")
    if not whole.isdecimal() or (dot and not part.isdecimal()) or len(part) > DIGITS:
        return None
    return int(whole) * MILLI + int((part + "000")[:3])


def baseline(card: MeterCard, period: date) -> tuple[date | None, int | None]:
    if card.last_period == period:
        values, since = card.prior_values, card.prior_period
    else:
        values, since = card.last_values, card.last_period
    return since, None if values is None else values.get(TariffZone.SINGLE)


def anomaly(card: MeterCard, period: date, value: int) -> str | None:
    since, previous = baseline(card, period)
    if previous is None:
        return None
    if value < previous:
        return "below"
    months = 1
    if since is not None:
        months = max(1, (period.year - since.year) * 12 + period.month - since.month)
    limit = TYPICAL_MONTH[card.meter.type] * MONTHLY_LIMIT_FACTOR * months * MILLI
    return "high" if value - previous > limit else None


class MeterPhotoService:
    __slots__ = ("_profile", "_readings")

    def __init__(
        self,
        profile_service: ProfileService,
        readings_service: ReadingsService,
    ) -> None:
        self._profile = profile_service
        self._readings = readings_service

    async def meters(self, user_id: UserId) -> PhotoMeters:
        residency = (await self._profile.me(user_id)).latest_residency
        if residency is None:
            return PhotoMeters(refusal=NO_HOUSE)
        if not residency.is_connected:
            return PhotoMeters(refusal=NOT_CONNECTED)
        resident = residency.resident
        if (
            resident.flat_id is None
            or resident.verified_at is None
            or resident.status is not ResidentStatus.ACTIVE
        ):
            return PhotoMeters(refusal=NOT_VERIFIED)
        flat_id = resident.flat_id
        cards = await self._readings.list_meters(flat_id)
        single = [
            card for card in cards if card.can_submit and card.meter.tariff_zones == 1
        ]
        if not single:
            two_tariff = any(card.meter.tariff_zones > 1 for card in cards)
            return PhotoMeters(refusal=TWO_TARIFF if two_tariff else NO_METERS)
        periods = await self._readings.periods(flat_id)
        period = next(
            (option.period for option in periods.options if option.is_open),
            None,
        )
        if period is None:
            return PhotoMeters(refusal=WINDOW_CLOSED)
        return PhotoMeters(flat_id=flat_id, period=period, cards=single)

    async def card(self, user_id: UserId, meter_id: MeterId) -> MeterCard:
        choice = await self.meters(user_id)
        card = next((card for card in choice.cards if card.meter.id == meter_id), None)
        if card is None:
            raise InvalidRequest(choice.refusal or UNKNOWN_METER)
        return card

    async def submit(
        self,
        user_id: UserId,
        meter_id: MeterId,
        period: date,
        value: int,
        photo: str,
        recognized: int | None,
    ) -> SubmitResult:
        await self.card(user_id, meter_id)
        return await self._readings.submit(
            user_id,
            meter_id,
            SubmitDraft(
                period=period,
                values={TariffZone.SINGLE: value},
                photos=[photo],
                ocr_used=recognized is not None,
                ocr_accepted=recognized == value,
            ),
            channel="bot",
        )
