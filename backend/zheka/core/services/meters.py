from datetime import UTC, date, datetime

from zheka.base import ZhekaType
from zheka.core.enums import MeterType
from zheka.core.errors import InvalidRequest, InvalidValue
from zheka.core.ids import FlatId, MeterId, UserId
from zheka.core.services.meter_access import MeterAccess, MeterCard
from zheka.infra.database.repos.meters import MetersRepo

METER_ALREADY_EXISTS = "У квартиры уже есть счетчик такого типа"
EMPTY_SERIAL = "Укажите номер счетчика"
INVALID_ZONE_COUNT = "У счетчика может быть одна или две тарифные зоны"

_VALID_ZONE_COUNTS = (1, 2)


class MeterDraft(ZhekaType):
    type: MeterType
    tariff_zones: int
    serial: str
    next_verification_date: date | None = None


class MeterUpdateDraft(ZhekaType):
    tariff_zones: int
    serial: str
    next_verification_date: date | None = None


def _checked_zone_count(count: int) -> None:
    if count not in _VALID_ZONE_COUNTS:
        raise InvalidValue(INVALID_ZONE_COUNT)


def _stated_serial(serial: str) -> str:
    stripped = serial.strip()
    if not stripped:
        raise InvalidRequest(EMPTY_SERIAL)
    return stripped


class MetersService:
    __slots__ = ("_access", "_meters")

    def __init__(self, meters_repo: MetersRepo, access: MeterAccess) -> None:
        self._meters = meters_repo
        self._access = access

    async def add(
        self,
        user_id: UserId,
        flat_id: FlatId,
        draft: MeterDraft,
    ) -> MeterCard:
        await self._access.can_manage_meter(user_id, flat_id)
        _checked_zone_count(draft.tariff_zones)
        serial = _stated_serial(draft.serial)

        # ON CONFLICT вместо read-then-write: два параллельных нажатия иначе
        # оба прошли бы проверку и оба вставили бы свою строку
        meter = await self._meters.add(
            flat_id,
            draft.type,
            draft.tariff_zones,
            serial,
            draft.next_verification_date,
        )
        if meter is None:
            raise InvalidValue(METER_ALREADY_EXISTS)
        return await self._access.meter_card(meter, datetime.now(UTC).date())

    async def update(
        self,
        user_id: UserId,
        meter_id: MeterId,
        draft: MeterUpdateDraft,
    ) -> MeterCard:
        meter = await self._access.get_meter(meter_id)
        await self._access.can_manage_meter(user_id, FlatId(meter.flat_id))
        _checked_zone_count(draft.tariff_zones)
        serial = _stated_serial(draft.serial)

        await self._meters.update(
            meter,
            draft.tariff_zones,
            serial,
            draft.next_verification_date,
        )
        return await self._access.meter_card(meter, datetime.now(UTC).date())
