from collections.abc import Mapping
from enum import StrEnum


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


SERVICE_LABELS: Mapping[ServiceType, str] = {
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

SERVICE_OF_METER: Mapping[MeterType, ServiceType] = {
    meter_type: ServiceType(meter_type) for meter_type in MeterType
}
