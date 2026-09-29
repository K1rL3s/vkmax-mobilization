from datetime import datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema, FreeText
from zheka.core.enums import PollStatus
from zheka.core.ids import FlatId, HouseId, PollId, PollOptionId
from zheka.core.models import Flat
from zheka.core.services.polls import (
    AdminPollListItemData,
    PollCardData,
    PollDraft,
    PollListItemData,
    PollOptionCount,
    PollResultsData,
)
from zheka.core.services.quorum import QUORUM_PERCENT, area_percent_of

DISCLAIMER = (
    "предварительный сбор позиций собственников, "
    "не является голосованием (ОСС) по ЖК РФ"
)

_PERCENT = "Доля в сотых долях процента, 50% это 5000"
_AREA = "Площадь в сотых долях квадратного метра"


class PollOptionItem(BaseSchema):
    id: PollOptionId
    text: str
    position: int


class PollListItem(BaseSchema):
    id: PollId
    title: str
    created_by_role: str
    status: PollStatus
    starts_at: datetime
    ends_at: datetime
    is_multiple: bool
    voted: bool
    voted_flats: int

    @classmethod
    def of(cls, data: PollListItemData | PollCardData) -> Self:
        poll = data.poll
        return cls(
            id=poll.id,
            title=poll.title,
            created_by_role=poll.created_by_role,
            status=data.status,
            starts_at=poll.starts_at,
            ends_at=poll.ends_at,
            is_multiple=poll.is_multiple,
            voted=data.voted,
            voted_flats=data.voted_flats,
        )


class PollCard(PollListItem):
    house_id: HouseId
    can_vote: bool
    can_manage: bool
    options: list[PollOptionItem]
    disclaimer: str = DISCLAIMER
    description: str | None = None
    my_option_ids: list[PollOptionId]
    is_oss: bool = False

    @classmethod
    def of_card(cls, data: PollCardData) -> Self:
        poll = data.poll
        return cls(
            **PollListItem.of(data).model_dump(),
            house_id=poll.house_id,
            can_vote=data.can_vote,
            can_manage=data.can_manage,
            options=[PollOptionItem.model_validate(option) for option in data.options],
            description=poll.description,
            my_option_ids=data.my_option_ids,
        )


class CreatePollRequest(BaseSchema):
    title: FreeText
    options: list[FreeText]
    ends_at: datetime
    description: FreeText | None = None
    is_multiple: bool = False

    def draft(self) -> PollDraft:
        return PollDraft(
            title=self.title,
            description=self.description,
            options=self.options,
            ends_at=self.ends_at,
            is_multiple=self.is_multiple,
        )


class CreateInitiativeRequest(BaseSchema):
    title: FreeText
    description: FreeText | None = None


class CreateOrgPollRequest(CreatePollRequest):
    house_id: HouseId
    notify_residents: bool = Field(
        default=False,
        description=(
            "Сообщить жителям дома в личные сообщения объявлением с кнопкой "
            "голосования; по нему УК видит реестр уведомлений"
        ),
    )


class VoteRequest(BaseSchema):
    option_ids: list[PollOptionId]


class PollOptionResult(BaseSchema):
    option_id: PollOptionId
    text: str
    flats_count: int
    area: int = Field(description=_AREA)
    area_percent: int = Field(description=_PERCENT)

    @classmethod
    def of(cls, count: PollOptionCount, total_area: int) -> Self:
        return cls(
            option_id=count.option.id,
            text=count.option.text,
            flats_count=count.flats_count,
            area=count.area,
            area_percent=area_percent_of(count.area, total_area),
        )


class PollResults(BaseSchema):
    poll_id: PollId
    status: PollStatus
    total_flats: int
    voted_flats: int
    total_area: int = Field(description=_AREA)
    voted_area: int = Field(description=_AREA)
    voted_area_percent: int = Field(description=_PERCENT)
    quorum_percent: int = Field(default=QUORUM_PERCENT, description=_PERCENT)
    quorum_reached: bool
    unverified_flats: int
    options: list[PollOptionResult]
    disclaimer: str = DISCLAIMER
    is_oss: bool = False
    flats_without_area: int

    @classmethod
    def of(cls, data: PollResultsData) -> Self:
        forecast = data.forecast
        return cls(
            poll_id=data.poll.id,
            status=data.status,
            total_flats=forecast.total_flats,
            voted_flats=forecast.voted_flats,
            total_area=forecast.total_area,
            voted_area=forecast.voted_area,
            voted_area_percent=forecast.area_percent,
            quorum_reached=forecast.quorum_reached,
            unverified_flats=forecast.unweighted_votes,
            options=[
                PollOptionResult.of(count, forecast.total_area)
                for count in data.options
            ],
            flats_without_area=data.flats_without_area,
        )


class PollNonVoterItem(BaseSchema):
    flat_id: FlatId
    flat_number: str
    entrance: int | None = None

    @classmethod
    def of(cls, flat: Flat) -> Self:
        return cls(
            flat_id=flat.id,
            flat_number=flat.number,
            entrance=flat.entrance,
        )


class AdminPollListItem(PollListItem):
    house_id: HouseId
    address: str

    @classmethod
    def of_admin(cls, data: AdminPollListItemData) -> Self:
        return cls(
            **PollListItem.of(data.item).model_dump(),
            house_id=data.item.poll.house_id,
            address=data.address,
        )
