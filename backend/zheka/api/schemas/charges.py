from datetime import date, datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.api.schemas.files import FileRef
from zheka.core.charges import ChargeLine as DomainChargeLine
from zheka.core.enums import SERVICE_LABELS, ServiceType
from zheka.core.ids import ChargeId, FlatId, MeterId, RequestId, TariffId
from zheka.core.models import Tariff
from zheka.core.services.charges import BreakdownData, BreakdownLine, ChargeCardData

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

    @classmethod
    def of(cls, tariff: Tariff, document: FileRef | None) -> Self:
        return cls(
            id=TariffId(tariff.id),
            service=tariff.service,
            label=SERVICE_LABELS[tariff.service],
            value=tariff.value,
            unit=tariff.unit,
            valid_from=tariff.valid_from,
            document=document,
        )


class ChargeLine(BaseSchema):
    service: ServiceType
    label: str
    amount: int = Field(description=_MONEY)
    volume: int | None = Field(default=None, description=_VOLUME)
    tariff: int | None = Field(default=None, description=_TARIFF)
    unit: str | None = None

    @classmethod
    def of(cls, line: DomainChargeLine) -> Self:
        return cls(
            service=line.service,
            label=SERVICE_LABELS[line.service],
            amount=line.amount,
            volume=line.volume,
            tariff=line.tariff,
            unit=line.unit,
        )


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
        default=None, description="Площадь в сотых долях квадратного метра"
    )

    @classmethod
    def of_card(cls, data: ChargeCardData) -> Self:
        return cls(
            **ChargeListItem.model_validate(data.charge).model_dump(),
            address=data.house.address,
            flat_number=data.flat.number,
            lines=[ChargeLine.of(line) for line in data.lines],
            flat_area=data.flat.area,
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

    @classmethod
    def of(cls, view: BreakdownLine) -> Self:
        delta = view.delta
        return cls(
            service=delta.service,
            label=SERVICE_LABELS[delta.service],
            amount=0 if view.current is None else view.current.amount,
            delta=delta.delta,
            tariff_effect=delta.tariff_effect,
            volume_effect=delta.volume_effect,
            appeared=delta.kind == "appeared",
            disappeared=delta.kind == "disappeared",
            previous_amount=None if view.previous is None else view.previous.amount,
        )


class ConsumptionPoint(BaseSchema):
    period: date
    consumption: int = Field(description=_VOLUME)


class ServiceConsumption(BaseSchema):
    service: ServiceType
    meter_id: MeterId
    points: list[ConsumptionPoint]
    house_average: int | None = Field(default=None, description=_VOLUME)


class ChargeBreakdown(BaseSchema):
    charge_id: ChargeId
    period: date
    total: int = Field(description=_MONEY)
    delta: int = Field(description=_MONEY)
    lines: list[ChargeBreakdownLine]
    previous_period: date | None = None
    previous_total: int | None = Field(default=None, description=_MONEY)
    consumption: list[ServiceConsumption] = Field(default_factory=list)

    @classmethod
    def of(cls, data: BreakdownData) -> Self:
        charge = data.charge
        previous = data.previous_charge
        return cls(
            charge_id=charge.id,
            period=charge.period,
            total=charge.total,
            delta=data.delta,
            lines=[ChargeBreakdownLine.of(line) for line in data.lines],
            previous_period=None if previous is None else previous.period,
            previous_total=None if previous is None else previous.total,
            consumption=[
                ServiceConsumption.model_validate(item) for item in data.consumption
            ],
        )


class DisputeChargeRequest(BaseSchema):
    comment: str
    service: ServiceType | None = None


class DisputeChargeResponse(BaseSchema):
    request_id: RequestId


class PayChargeResponse(BaseSchema):
    charge_id: ChargeId
    paid_at: datetime
    is_demo: bool = Field(
        default=True, description="Демонстрация, платеж не проводится"
    )
