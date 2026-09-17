from datetime import date, datetime

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.files import FileRef
from zheka.core.enums import ServiceType
from zheka.core.ids import ChargeId, FlatId, RequestId, TariffId

_MONEY = "Сумма в копейках"
_TARIFF = "Тариф в 1/10000 рубля за единицу"
_VOLUME = "Объем в тысячных долях единицы измерения"


class TariffItem(BaseSchema):
    id: TariffId
    service: ServiceType
    label: str
    value: int = Field(description=_TARIFF)
    unit: str
    valid_from: date
    document: FileRef | None = None


class ChargeLine(BaseSchema):
    service: ServiceType
    label: str
    amount: int = Field(description=_MONEY)
    volume: int | None = Field(default=None, description=_VOLUME)
    tariff: int | None = Field(default=None, description=_TARIFF)
    unit: str | None = None


class ChargeListItem(BaseSchema):
    id: ChargeId
    flat_id: FlatId
    period: date
    total: int = Field(description=_MONEY)
    is_closed: bool
    paid_at: datetime | None = None


class ChargeCard(ChargeListItem):
    address: str
    flat_number: str
    lines: list[ChargeLine]
    flat_area: int | None = Field(
        default=None,
        description="Площадь в сотых долях квадратного метра",
    )


class ChargeBreakdownLine(BaseSchema):
    service: ServiceType
    label: str
    amount: int = Field(description=_MONEY)
    delta: int = Field(description=_MONEY)
    # дельта раскладывается на тарифный и расходный эффект
    tariff_effect: int = Field(description=_MONEY)
    volume_effect: int = Field(description=_MONEY)
    appeared: bool
    disappeared: bool
    previous_amount: int | None = Field(default=None, description=_MONEY)


class ChargeBreakdown(BaseSchema):
    charge_id: ChargeId
    period: date
    total: int = Field(description=_MONEY)
    delta: int = Field(description=_MONEY)
    lines: list[ChargeBreakdownLine]
    previous_period: date | None = None
    previous_total: int | None = Field(default=None, description=_MONEY)


class DisputeChargeRequest(BaseSchema):
    comment: str
    service: ServiceType | None = None


class DisputeChargeResponse(BaseSchema):
    request_id: RequestId


class PayChargeResponse(BaseSchema):
    charge_id: ChargeId
    paid_at: datetime
    # оплата демонстрационная, денег не движется
    is_demo: bool = True
