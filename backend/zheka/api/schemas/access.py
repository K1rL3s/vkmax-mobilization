from datetime import date, datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.ids import AccessRequestId, AccessSlotId, FlatId, HouseId
from zheka.core.services.access import (
    AccessGridData,
    AccessRequestData,
    AccessSlotData,
    AccessTargetData,
)


class AccessSlotItem(BaseSchema):
    id: AccessSlotId
    starts_at: datetime
    capacity: int = Field(description="Сколько квартир помещается в окно")
    taken: int = Field(description="Сколько квартир уже выбрали это окно")

    @classmethod
    def of(cls, data: AccessSlotData) -> Self:
        return cls(
            id=AccessSlotId(data.slot.id),
            starts_at=data.slot.starts_at,
            capacity=data.slot.capacity,
            taken=data.taken,
        )


class AccessRequestItem(BaseSchema):
    id: AccessRequestId
    created_at: datetime
    house_id: HouseId
    address: str
    reason: str
    date: date
    slots: list[AccessSlotItem]
    responded_count: int
    targets_count: int
    my_flat_id: FlatId | None = None
    my_slot_id: AccessSlotId | None = None

    @classmethod
    def of(cls, data: AccessRequestData) -> Self:
        request = data.request
        return cls(
            id=request.id,
            created_at=request.created_at,
            house_id=request.house_id,
            address=data.house.address,
            reason=request.reason,
            date=request.date,
            slots=[AccessSlotItem.of(slot) for slot in data.slots],
            responded_count=data.responded_count,
            targets_count=data.targets_count,
            my_flat_id=data.my_flat_id,
            my_slot_id=data.my_slot_id,
        )


class AccessSlotInput(BaseSchema):
    starts_at: datetime
    capacity: int = Field(description="Сколько квартир помещается в окно")


class CreateAccessRequestRequest(BaseSchema):
    house_id: HouseId
    reason: str
    date: date
    flat_ids: list[FlatId]
    slots: list[AccessSlotInput]


class AccessTargetCell(BaseSchema):
    flat_id: FlatId
    flat_number: str
    slot_id: AccessSlotId | None = None
    responded_at: datetime | None = None

    @classmethod
    def of(cls, data: AccessTargetData) -> Self:
        target = data.target
        return cls(
            flat_id=target.flat_id,
            flat_number=data.flat_number,
            slot_id=target.slot_id,
            responded_at=target.responded_at,
        )


class AccessRequestGrid(BaseSchema):
    access_request: AccessRequestItem
    targets: list[AccessTargetCell]
    flats_without_residents: list[FlatId] = Field(
        default=[],
        description=(
            "Квартиры, которым не досталось ячейки: в них некому ответить - "
            "подтвержденного жителя нет вовсе или он заблокирован УК. "
            "Заполняется только при создании запроса"
        ),
    )

    @classmethod
    def of(cls, data: AccessGridData) -> Self:
        return cls(
            access_request=AccessRequestItem.of(data.request),
            targets=[AccessTargetCell.of(target) for target in data.targets],
            flats_without_residents=list(data.flats_without_residents),
        )
