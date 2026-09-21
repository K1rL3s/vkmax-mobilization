from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentResidencyDep
from zheka.api.schemas.announcements import AnnouncementItem
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.core.services.announcements import AnnouncementsService

router = APIRouter(tags=["Объявления"], route_class=DishkaRoute)


@router.get("/announcements", summary="Объявления УК по дому")
async def list_announcements(
    residency: CurrentResidencyDep,
    announcements_service: FromDishka[AnnouncementsService],
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AnnouncementItem]:
    items, total = await announcements_service.list_for_resident(
        residency.house_id, limit, offset
    )
    return Page(items=[AnnouncementItem.of(item) for item in items], total=total)
