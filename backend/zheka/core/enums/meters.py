from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class MeterType(StrEnum):
    HOT_WATER = "hot_water"
    COLD_WATER = "cold_water"
    ELECTRICITY = "electricity"
    GAS = "gas"
    HEATING = "heating"


class TariffZone(StrEnum):
    SINGLE = "single"
    DAY = "day"
    NIGHT = "night"


class ServiceType(StrEnum):
    COLD_WATER = "cold_water"
    HOT_WATER = "hot_water"
    ELECTRICITY = "electricity"
    GAS = "gas"
    HEATING = "heating"
    MAINTENANCE = "maintenance"
    OVERHAUL = "overhaul"
    WASTE = "waste"
    PENALTY = "penalty"
    RECALCULATION = "recalculation"


# русские названия услуг для квитанции, тарифа и разбора начисления - единая
# таблица, чтобы литерал не разъезжался по местам вызова
SERVICE_LABELS: Mapping[ServiceType, str] = MappingProxyType(
    {
        ServiceType.COLD_WATER: "Холодная вода",
        ServiceType.HOT_WATER: "Горячая вода",
        ServiceType.ELECTRICITY: "Электроэнергия",
        ServiceType.GAS: "Газ",
        ServiceType.HEATING: "Отопление",
        ServiceType.MAINTENANCE: "Содержание жилья",
        ServiceType.OVERHAUL: "Капитальный ремонт",
        ServiceType.WASTE: "Обращение с ТКО",
        ServiceType.PENALTY: "Пени",
        ServiceType.RECALCULATION: "Перерасчет",
    }
)

# счетчик какого типа считает расход по какой услуге тарифа - используется и
# предварительным расчетом при подаче показания, и разбором начисления
SERVICE_OF_METER: Mapping[MeterType, ServiceType] = MappingProxyType(
    {
        MeterType.HOT_WATER: ServiceType.HOT_WATER,
        MeterType.COLD_WATER: ServiceType.COLD_WATER,
        MeterType.ELECTRICITY: ServiceType.ELECTRICITY,
        MeterType.GAS: ServiceType.GAS,
        MeterType.HEATING: ServiceType.HEATING,
    }
)
