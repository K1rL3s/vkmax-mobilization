from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import AdminOrgDep, CurrentOrgDep, IdempotencyDep
from zheka.api.schemas.announcements import (
    AnnouncementItem,
    CreateAnnouncementRequest,
    NoticeRegister,
)
from zheka.api.schemas.base import Limit, Offset, OkResponse, Page
from zheka.core.ids import AnnouncementId, HouseId, PollId
from zheka.core.services.announcements import AnnouncementsService
from zheka.core.services.files import FilesService

router = APIRouter(tags=["Админка: объявления"], route_class=DishkaRoute)


@router.get("/admin/announcements", summary="Объявления организации")
async def list_org_announcements(
    current_org: CurrentOrgDep,
    announcements_service: FromDishka[AnnouncementsService],
    files_service: FromDishka[FilesService],
    house_id: HouseId | None = None,
    poll_id: PollId | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AnnouncementItem]:
    items, total = await announcements_service.list_for_org(
        current_org.org_id,
        house_id,
        poll_id,
        limit,
        offset,
    )
    return Page(
        items=[AnnouncementItem.of(item, files_service) for item in items],
        total=total,
    )


@router.post("/admin/announcements", summary="Создать объявление")
async def create_announcement(
    current_org: CurrentOrgDep,
    body: CreateAnnouncementRequest,
    announcements_service: FromDishka[AnnouncementsService],
    files_service: FromDishka[FilesService],
    idempotency: IdempotencyDep,
) -> AnnouncementItem:
    saved = await idempotency.replay(AnnouncementItem)
    if saved is not None:
        return saved
    data = await announcements_service.create(
        current_org.org_id,
        current_org.user_id,
        body.house_ids,
        body.text,
        body.channels,
        urgent=body.urgent,
        entrances=body.entrances,
        flat_ids=body.flat_ids,
        works=None if body.works is None else body.works.draft(),
        documents=[document.model_dump() for document in body.documents],
    )
    response = AnnouncementItem.of(data, files_service)
    await idempotency.save(response)
    return response


@router.get(
    "/admin/announcements/{announcement_id}/register",
    summary="Реестр уведомлений по объявлению",
    description=(
        "Квартиры одного дома объявления (house_id, по умолчанию первый) и "
        "статус личного сообщения каждому жителю. Только администратору УК"
    ),
)
async def notice_register(
    current_org: AdminOrgDep,
    announcement_id: AnnouncementId,
    announcements_service: FromDishka[AnnouncementsService],
    files_service: FromDishka[FilesService],
    house_id: HouseId | None = None,
) -> NoticeRegister:
    data = await announcements_service.register(
        current_org.org_id,
        announcement_id,
        house_id,
    )
    return NoticeRegister.of(data, files_service, is_demo=current_org.is_demo)


@router.post(
    "/admin/announcements/{announcement_id}/finish",
    summary="Завершить плановые работы досрочно",
    description=(
        "Окончание работ становится текущим моментом, жители получают "
        "без звука «Работы завершены» в те же каналы. Только для идущих работ; "
        "в демо-УК - 403 на чужие работы"
    ),
)
async def finish_works(
    current_org: CurrentOrgDep,
    announcement_id: AnnouncementId,
    announcements_service: FromDishka[AnnouncementsService],
    files_service: FromDishka[FilesService],
) -> AnnouncementItem:
    data = await announcements_service.finish_works(
        current_org.org_id,
        announcement_id,
        current_org.user_id,
    )
    return AnnouncementItem.of(data, files_service)


@router.post(
    "/admin/announcements/{announcement_id}/register/pdf",
    summary="Реестр уведомлений файлом в чат с ботом",
    description=(
        "Реестр дома (house_id, по умолчанию первый) PDF-файлом в чат "
        "администратора с ботом, unmarked_only оставляет квартиры без отметки. "
        "Чужое объявление или дом не из объявления - 404, бот не может написать "
        "администратору (нет чата с ботом или бот остановлен) - 409. Только "
        "администратору УК; на демо-УК - с пометкой «ДЕМО»"
    ),
)
async def send_register_pdf(
    current_org: AdminOrgDep,
    announcement_id: AnnouncementId,
    announcements_service: FromDishka[AnnouncementsService],
    house_id: HouseId | None = None,
    unmarked_only: bool = False,
) -> OkResponse:
    await announcements_service.send_register_pdf(
        current_org.org_id,
        current_org.user_id,
        announcement_id,
        house_id,
        unmarked_only=unmarked_only,
    )
    return OkResponse()
