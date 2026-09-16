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
