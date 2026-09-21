from datetime import UTC, date, datetime

from zheka.base import ZhekaType
from zheka.core.enums import MeterType
from zheka.core.errors import InvalidRequest, InvalidValue
from zheka.core.ids import FlatId, MeterId, UserId
from zheka.core.services.meter_access import MeterAccess, MeterCard
from zheka.infra.database.repos.meters import MetersRepo


class MeterUpdateDraft(ZhekaType):
    tariff_zones: int
    serial: str
    next_verification_date: date | None = None

    def checked_serial(self) -> str:
        if self.tariff_zones not in {1, 2}:
            raise InvalidValue("У счетчика может быть одна или две тарифные зоны")
        serial = self.serial.strip()
        if not serial:
            raise InvalidRequest("Укажите номер счетчика")
        return serial


class MeterDraft(MeterUpdateDraft):
    type: MeterType


class MetersService:
    __slots__ = ("_access", "_meters")

    def __init__(self, meters_repo: MetersRepo, access: MeterAccess) -> None:
        self._meters = meters_repo
        self._access = access

    async def add(
        self, user_id: UserId, flat_id: FlatId, draft: MeterDraft
    ) -> MeterCard:
        await self._access.can_manage_meter(user_id, flat_id)
        serial = draft.checked_serial()

        meter = await self._meters.add(
            flat_id,
            draft.type,
            draft.tariff_zones,
            serial,
            draft.next_verification_date,
        )
        if meter is None:
            raise InvalidValue("У квартиры уже есть счетчик такого типа")
        return await self._access.meter_card(meter, datetime.now(UTC))

    async def update(
        self, user_id: UserId, meter_id: MeterId, draft: MeterUpdateDraft
    ) -> MeterCard:
        meter = await self._access.get_meter(meter_id)
        await self._access.can_manage_meter(user_id, meter.flat_id)
        serial = draft.checked_serial()

        await self._meters.update(
            meter, draft.tariff_zones, serial, draft.next_verification_date
        )
        return await self._access.meter_card(meter, datetime.now(UTC))
