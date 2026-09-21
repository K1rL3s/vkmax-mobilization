from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentOrgDep
from zheka.api.schemas.announcements import AnnouncementItem, CreateAnnouncementRequest
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.core.ids import HouseId
from zheka.core.services.announcements import AnnouncementsService

router = APIRouter(tags=["Админка: объявления"], route_class=DishkaRoute)


@router.get("/admin/announcements", summary="Объявления организации")
async def list_org_announcements(
    current_org: CurrentOrgDep,
    announcements_service: FromDishka[AnnouncementsService],
    house_id: HouseId | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AnnouncementItem]:
    items, total = await announcements_service.list_for_org(
        current_org.org_id, house_id, limit, offset
    )
    return Page(items=[AnnouncementItem.of(item) for item in items], total=total)


@router.post("/admin/announcements", summary="Создать объявление")
async def create_announcement(
    current_org: CurrentOrgDep,
    body: CreateAnnouncementRequest,
    announcements_service: FromDishka[AnnouncementsService],
) -> AnnouncementItem:
    data = await announcements_service.create(
        current_org.org_id,
        current_org.user_id,
        body.house_ids,
        body.text,
        body.channels,
    )
    return AnnouncementItem.of(data)
