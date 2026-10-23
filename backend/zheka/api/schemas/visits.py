from datetime import date, datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.ids import AccessRequestId, AccessSlotId
from zheka.core.services.visit_card import VisitData, VisitWindow


class VisitWindowItem(BaseSchema):
    id: AccessSlotId
    starts_at: datetime
    minutes: int = Field(description="Длина окна, минут")

    @classmethod
    def of(cls, window: VisitWindow) -> Self:
        return cls(id=window.id, starts_at=window.starts_at, minutes=window.minutes)


class VisitItem(BaseSchema):
    id: AccessRequestId
    date: date
    windows: list[VisitWindowItem]
    slot_id: AccessSlotId | None = Field(
        default=None,
        description="Окно, выбранное жителем; пусто - житель еще не выбрал",
    )

    @classmethod
    def of(cls, data: VisitData) -> Self:
        return cls(
            id=data.id,
            date=data.visit.date,
            windows=[VisitWindowItem.of(window) for window in data.windows],
            slot_id=data.slot_id,
        )


class ProposeVisitRequest(BaseSchema):
    date: date
    starts: list[datetime] = Field(
        description="Начала окон в местном времени дома, от 1 до 5, все в один день",
    )
    minutes: int = Field(description="Длина каждого окна, минут")
