from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentResidencyDep
from zheka.api.schemas.announcements import AnnouncementItem
from zheka.api.schemas.base import Limit, Offset, Page

router = APIRouter(tags=["Объявления"], route_class=DishkaRoute)


@router.get("/announcements", summary="Объявления УК по дому")
async def list_announcements(
    residency: CurrentResidencyDep,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AnnouncementItem]:
    raise NotImplementedError("ещё не реализовано")
