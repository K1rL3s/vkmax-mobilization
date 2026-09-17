from datetime import date, datetime

from zheka.api.schemas.base import BaseSchema
from zheka.core.ids import AccessRequestId, AccessSlotId, FlatId, HouseId


class AccessSlotItem(BaseSchema):
    id: AccessSlotId
    starts_at: datetime
    capacity: int
    taken: int


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
    # заполняется только в списке жителя
    my_flat_id: FlatId | None = None
    my_slot_id: AccessSlotId | None = None


class AccessSlotInput(BaseSchema):
    starts_at: datetime
    capacity: int


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


class AccessRequestGrid(BaseSchema):
    access_request: AccessRequestItem
    targets: list[AccessTargetCell]
