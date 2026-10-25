from collections.abc import Mapping

from zheka.base import ZhekaType
from zheka.core.enums import RequestCategory, ServiceType

MONTHLY_NORM_HOURS: Mapping[ServiceType, int] = {
    ServiceType.COLD_WATER: 8,
    ServiceType.HOT_WATER: 8,
    ServiceType.ELECTRICITY: 24,
    ServiceType.GAS: 4,
    ServiceType.HEATING: 24,
}
CATEGORY_SERVICE: Mapping[RequestCategory, ServiceType] = {
    RequestCategory.WATER_SUPPLY: ServiceType.COLD_WATER,
    RequestCategory.HEATING: ServiceType.HEATING,
    RequestCategory.ELECTRICITY: ServiceType.ELECTRICITY,
}
HEATING_OFF_MONTHS = range(5, 10)
RATE_PER_HOUR = 15
WHOLE = 10_000


class Recalculation(ZhekaType):
    hours_over: int
    amount: int


def recalculation(service: ServiceType, month_hours: int, charge: int) -> Recalculation:
    hours_over = max(0, month_hours - MONTHLY_NORM_HOURS[service])
    share = min(hours_over * RATE_PER_HOUR, WHOLE)
    return Recalculation(hours_over=hours_over, amount=charge * share // WHOLE)
