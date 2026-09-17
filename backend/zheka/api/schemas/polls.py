from datetime import datetime

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import PollStatus
from zheka.core.ids import FlatId, HouseId, PollId, PollOptionId

# 50% площади дома в сотых долях процента
QUORUM_PERCENT = 5000

_PERCENT = "Доля в сотых долях процента, 50% это 5000"


class PollOptionItem(BaseSchema):
    id: PollOptionId
    text: str
    position: int


class PollListItem(BaseSchema):
    id: PollId
    title: str
    status: PollStatus
    starts_at: datetime
    ends_at: datetime
    is_multiple: bool
    voted: bool
    voted_flats: int


class PollCard(PollListItem):
    house_id: HouseId
    created_by_role: str
    can_vote: bool
    options: list[PollOptionItem]
    # опрос не является ОСС по ЖК РФ
    disclaimer: str
    description: str | None = None
    my_option_ids: list[PollOptionId]


class CreatePollRequest(BaseSchema):
    title: str
    options: list[str]
    ends_at: datetime
    description: str | None = None
    is_multiple: bool = False


class CreateOrgPollRequest(CreatePollRequest):
    house_id: HouseId


class VoteRequest(BaseSchema):
    option_ids: list[PollOptionId]


class PollOptionResult(BaseSchema):
    option_id: PollOptionId
    text: str
    flats_count: int
    area: int = Field(description="Площадь в сотых долях квадратного метра")
    area_percent: int = Field(description=_PERCENT)


class PollResults(BaseSchema):
    poll_id: PollId
    status: PollStatus
    total_flats: int
    voted_flats: int
    total_area: int = Field(description="Площадь в сотых долях квадратного метра")
    voted_area: int = Field(description="Площадь в сотых долях квадратного метра")
    voted_area_percent: int = Field(description=_PERCENT)
    quorum_percent: int = Field(default=QUORUM_PERCENT, description=_PERCENT)
    quorum_reached: bool
    # в площадь идут только подтвержденные квартиры
    unverified_flats: int
    options: list[PollOptionResult]
    disclaimer: str


class PollNonVoterItem(BaseSchema):
    flat_id: FlatId
    flat_number: str
    entrance: int | None = None


class AdminPollListItem(PollListItem):
    house_id: HouseId
    address: str
