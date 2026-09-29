from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentResidencyDep
from zheka.api.schemas.announcements import AnnouncementItem
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.core.services.announcements import AnnouncementsService
from zheka.core.services.files import FilesService

router = APIRouter(tags=["Объявления"], route_class=DishkaRoute)


@router.get("/announcements", summary="Объявления УК по дому")
async def list_announcements(
    residency: CurrentResidencyDep,
    announcements_service: FromDishka[AnnouncementsService],
    files_service: FromDishka[FilesService],
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AnnouncementItem]:
    items, total = await announcements_service.list_for_resident(
        residency.house_id,
        residency.flat_id,
        residency.verified,
        limit,
        offset,
    )
    return Page(
        items=[AnnouncementItem.of(item, files_service) for item in items],
        total=total,
    )
