from datetime import datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import HouseState
from zheka.core.ids import AnnouncementId, HouseId, PollId
from zheka.core.services.admin_map import AdminMapData, AdminMapRow


class AdminMapHouse(BaseSchema):
    id: HouseId
    lat: float
    lon: float
    address: str
    building: str
    state: HouseState = Field(
        description="Худшее состояние заявок: авария, эскалация, просрочка, "
        "открытые, спокойно",
    )
    open: int = Field(description="Незакрытые заявки")
    overdue: int = Field(description="Просроченные заявки")
    escalated: int = Field(description="Просроченные заявки с эскалацией жителя")
    grouped: int = Field(description="Незакрытые заявки в групповых")
    emergency: int = Field(
        description="Незакрытые заявки о протечке, кроме тех, что на приемке",
    )
    period_requests: int = Field(description="Заявки, созданные за период")
    rating: int | None = Field(
        default=None,
        description="Средняя оценка заявок за период в сотых долях балла",
    )
    urgent_id: AnnouncementId | None = None
    urgent_text: str | None = None
    urgent_at: datetime | None = None
    poll_id: PollId | None = None
    poll_title: str | None = None
    poll_ends_at: datetime | None = None
    poll_turnout: int | None = Field(
        default=None,
        description="Доля проголосовавших квартир в сотых долях процента, 50% это 5000",
    )
    appointments_today: int = Field(description="Записи на прием на сегодня")
    meters_percent: int | None = Field(
        default=None,
        description="Доля квартир со счетчиками, подавших показания за период, "
        "в сотых долях процента",
    )
    meters_submitted: int | None = None
    meters_flats: int | None = Field(
        default=None,
        description="Квартиры со счетчиками",
    )
    flats_count: int = Field(description="Все квартиры дома")
    residents_count: int | None = Field(
        default=None,
        description="Только для администратора",
    )
    verified_residents: int | None = Field(
        default=None,
        description="Только для администратора",
    )
    pending_verifications: int | None = Field(
        default=None,
        description="Только для администратора",
    )
    chat_bound: bool | None = Field(
        default=None,
        description="Только для администратора",
    )

    @classmethod
    def of(cls, row: AdminMapRow) -> Self:
        counts = row.counts
        return cls(
            id=row.house.id,
            lat=row.house.lat,
            lon=row.house.lon,
            address=row.house.address,
            building=row.house.building,
            state=counts.state,
            open=counts.open,
            overdue=counts.overdue,
            escalated=counts.escalated,
            grouped=counts.grouped,
            emergency=counts.emergency,
            period_requests=counts.period_requests,
            rating=counts.rating,
            urgent_id=None if row.urgent is None else row.urgent.announcement_id,
            urgent_text=None if row.urgent is None else row.urgent.text,
            urgent_at=None if row.urgent is None else row.urgent.created_at,
            poll_id=None if row.poll is None else row.poll.poll_id,
            poll_title=None if row.poll is None else row.poll.title,
            poll_ends_at=None if row.poll is None else row.poll.ends_at,
            poll_turnout=row.poll_turnout,
            appointments_today=row.appointments_today,
            meters_percent=None if row.meters is None else row.meters.percent,
            meters_submitted=None if row.meters is None else row.meters.submitted,
            meters_flats=None if row.meters is None else row.meters.flats_total,
            flats_count=row.flats_count,
            residents_count=row.residents_count,
            verified_residents=row.verified_residents,
            pending_verifications=row.pending_verifications,
            chat_bound=row.chat_bound,
        )


class AdminMapResponse(BaseSchema):
    items: list[AdminMapHouse]
    total: int
    without_coords: int = Field(description="Дома под фильтрами без координат")

    @classmethod
    def of(cls, data: AdminMapData) -> Self:
        items = [AdminMapHouse.of(row) for row in data.items]
        return cls(items=items, total=len(items), without_coords=data.without_coords)
