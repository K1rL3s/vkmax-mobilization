from datetime import date, datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.files import PHOTOS_DESCRIPTION, FileRef
from zheka.core.enums import MeterType, RequestCategory, TariffZone
from zheka.core.ids import FlatId, MeterId, ReadingId
from zheka.core.services.meter_access import MeterCard
from zheka.core.services.readings import PeriodOption

_READING = "Показание в тысячных долях единицы измерения"
_CONSUMPTION = "Расход в тысячных долях единицы измерения"
_AMOUNT = "Сумма в копейках, предварительный расчет, итог в квитанции"


class MeterItem(BaseSchema):
    id: MeterId
    flat_id: FlatId
    type: MeterType
    tariff_zones: int
    serial: str
    can_submit: bool
    verification_expired: bool
    next_verification_date: date | None = None
    last_period: date | None = None
    last_values: dict[TariffZone, int] | None = Field(
        default=None,
        description=_READING,
    )
    prior_period: date | None = None
    prior_values: dict[TariffZone, int] | None = Field(
        default=None,
        description=_READING,
    )

    @classmethod
    def of(cls, card: MeterCard) -> Self:
        meter = card.meter
        return cls(
            id=MeterId(meter.id),
            flat_id=FlatId(meter.flat_id),
            type=meter.type,
            tariff_zones=meter.tariff_zones,
            serial=meter.serial,
            can_submit=card.can_submit,
            verification_expired=card.verification_expired,
            next_verification_date=meter.next_verification_date,
            last_period=card.last_period,
            last_values=card.last_values,
            prior_period=card.prior_period,
            prior_values=card.prior_values,
        )


class ReadingPeriodItem(BaseSchema):
    period: date
    is_open: bool
    is_submitted: bool
    reason: str | None = None

    @classmethod
    def of(cls, option: PeriodOption, *, is_submitted: bool) -> Self:
        return cls(
            period=option.period,
            is_open=option.is_open,
            is_submitted=is_submitted,
            reason=option.reason,
        )


class ReadingItem(BaseSchema):
    id: ReadingId
    meter_id: MeterId
    period: date
    values: dict[TariffZone, int] = Field(description=_READING)
    consumption: dict[TariffZone, int] = Field(description=_CONSUMPTION)
    photos: list[FileRef]
    is_below_previous: bool
    ocr_used: bool
    submitted_at: datetime
    amount: int | None = Field(default=None, description=_AMOUNT)


class SubmitReadingRequest(BaseSchema):
    period: date
    values: dict[TariffZone, int] = Field(description=_READING)
    photos: list[str] = Field(default_factory=list, description=PHOTOS_DESCRIPTION)
    ocr_used: bool = False
    ocr_accepted: bool = False


class SubmitReadingResponse(BaseSchema):
    reading: ReadingItem
    house_average: int | None = Field(default=None, description=_CONSUMPTION)
    warning: str | None = None
    suggested_category: RequestCategory | None = None


class RecognizeReadingRequest(BaseSchema):
    photo_path: str
    meter_type: MeterType


class RecognizeReadingResponse(BaseSchema):
    values: dict[TariffZone, int] | None = Field(default=None, description=_READING)


class AddMeterRequest(BaseSchema):
    type: MeterType
    tariff_zones: int
    serial: str
    next_verification_date: date | None = None


class UpdateMeterRequest(BaseSchema):
    tariff_zones: int
    serial: str
    next_verification_date: date | None = None


class AdminReadingItem(BaseSchema):
    id: ReadingId
    meter_id: MeterId
    meter_type: MeterType
    serial: str
    flat_id: FlatId
    flat_number: str
    period: date
    values: dict[TariffZone, int] = Field(description=_READING)
    consumption: dict[TariffZone, int] = Field(description=_CONSUMPTION)
    photos: list[FileRef]
    is_below_previous: bool
    ocr_used: bool
    submitted_at: datetime
    submitted_by_name: str
