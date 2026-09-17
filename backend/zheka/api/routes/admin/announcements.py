from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentOrgDep
from zheka.api.schemas.announcements import (
    AnnouncementItem,
    CreateAnnouncementRequest,
)
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.core.ids import HouseId

router = APIRouter(tags=["Админка: объявления"], route_class=DishkaRoute)


@router.get("/admin/announcements", summary="Объявления организации")
async def list_org_announcements(
    current_org: CurrentOrgDep,
    house_id: HouseId | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AnnouncementItem]:
    raise NotImplementedError("ещё не реализовано")


@router.post("/admin/announcements", summary="Создать объявление")
async def create_announcement(
    current_org: CurrentOrgDep,
    body: CreateAnnouncementRequest,
) -> AnnouncementItem:
    raise NotImplementedError("ещё не реализовано")
