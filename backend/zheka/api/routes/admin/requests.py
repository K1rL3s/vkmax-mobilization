from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentOrgDep
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.files import FileRef
from zheka.api.schemas.requests import (
    AdminRequestCard,
    AdminRequestListItem,
    AssignExecutorRequest,
    ChangeGroupStatusRequest,
    ChangeRequestStatusRequest,
    CreatePhoneRequestRequest,
    ExecutorItem,
    ReplyToRequestRequest,
    RequestGroupCard,
)
from zheka.core.enums import RequestCategory, RequestChannel, RequestStatus
from zheka.core.ids import HouseId, RequestGroupId, RequestId, UserId
from zheka.core.services.admin_requests import (
    AdminRequestCardData,
    AdminRequestsService,
    PhoneRequestDraft,
)
from zheka.core.services.files import FilesService
from zheka.infra.database.repos.requests import RequestFilters

router = APIRouter(tags=["Админка: заявки"], route_class=DishkaRoute)


def _card(data: AdminRequestCardData, files_service: FilesService) -> AdminRequestCard:
    return AdminRequestCard.of_admin(
        data,
        [
            FileRef(name=photo.path, url=files_service.sign(photo.path))
            for photo in data.card.issue_photos
        ],
        [
            FileRef(name=photo.path, url=files_service.sign(photo.path))
            for photo in data.card.result_photos
        ],
    )


@router.get("/admin/requests", summary="Входящие заявки организации")
async def list_org_requests(
    current_org: CurrentOrgDep,
    admin_requests_service: FromDishka[AdminRequestsService],
    status: RequestStatus | None = None,
    category: RequestCategory | None = None,
    channel: RequestChannel | None = None,
    house_id: HouseId | None = None,
    executor_user_id: UserId | None = None,
    overdue: bool = False,
    grouped: bool = False,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AdminRequestListItem]:
    rows, total = await admin_requests_service.inbox(
        current_org.org_id,
        RequestFilters(
            house_id=house_id,
            category=category,
            status=status,
            channel=channel,
            executor_user_id=executor_user_id,
            overdue=overdue,
            grouped=grouped,
        ),
        limit,
        offset,
    )
    return Page(
        items=[AdminRequestListItem.of_admin(row) for row in rows],
        total=total,
    )


@router.get("/admin/requests/{request_id}", summary="Карточка заявки в админке")
async def get_org_request(
    request_id: RequestId,
    current_org: CurrentOrgDep,
    admin_requests_service: FromDishka[AdminRequestsService],
    files_service: FromDishka[FilesService],
) -> AdminRequestCard:
    data = await admin_requests_service.card(current_org.org_id, request_id)
    return _card(data, files_service)


@router.post("/admin/requests/{request_id}/status", summary="Сменить статус заявки")
async def change_request_status(
    request_id: RequestId,
    current_org: CurrentOrgDep,
    admin_requests_service: FromDishka[AdminRequestsService],
    files_service: FromDishka[FilesService],
    body: ChangeRequestStatusRequest,
) -> AdminRequestCard:
    data = await admin_requests_service.change_status(
        current_org.org_id,
        request_id,
        body.status,
        body.comment,
        current_org.user_id,
    )
    return _card(data, files_service)


@router.post("/admin/requests/{request_id}/reply", summary="Ответить жителю")
async def reply_to_request(
    request_id: RequestId,
    current_org: CurrentOrgDep,
    admin_requests_service: FromDishka[AdminRequestsService],
    files_service: FromDishka[FilesService],
    body: ReplyToRequestRequest,
) -> AdminRequestCard:
    data = await admin_requests_service.reply(
        current_org.org_id,
        request_id,
        body.text,
        current_org.user_id,
    )
    return _card(data, files_service)


@router.post("/admin/requests/{request_id}/assign", summary="Назначить исполнителя")
async def assign_request_executor(
    request_id: RequestId,
    current_org: CurrentOrgDep,
    admin_requests_service: FromDishka[AdminRequestsService],
    files_service: FromDishka[FilesService],
    body: AssignExecutorRequest,
) -> AdminRequestCard:
    data = await admin_requests_service.assign(
        current_org.org_id,
        request_id,
        body.user_id,
        current_org.user_id,
    )
    return _card(data, files_service)


@router.get("/admin/request-groups/{group_id}", summary="Группа заявок")
async def get_request_group(
    group_id: RequestGroupId,
    current_org: CurrentOrgDep,
    admin_requests_service: FromDishka[AdminRequestsService],
) -> RequestGroupCard:
    data = await admin_requests_service.group_card(current_org.org_id, group_id)
    return RequestGroupCard.of(data)


@router.post(
    "/admin/request-groups/{group_id}/status",
    summary="Сменить статус всей группе",
)
async def change_request_group_status(
    group_id: RequestGroupId,
    current_org: CurrentOrgDep,
    admin_requests_service: FromDishka[AdminRequestsService],
    body: ChangeGroupStatusRequest,
) -> RequestGroupCard:
    data = await admin_requests_service.change_group_status(
        current_org.org_id,
        group_id,
        body.status,
        body.comment,
        current_org.user_id,
    )
    return RequestGroupCard.of(data)


@router.post("/admin/requests/phone", summary="Заявка по звонку")
async def create_phone_request(
    current_org: CurrentOrgDep,
    admin_requests_service: FromDishka[AdminRequestsService],
    files_service: FromDishka[FilesService],
    body: CreatePhoneRequestRequest,
) -> AdminRequestCard:
    data = await admin_requests_service.create_phone(
        current_org.org_id,
        PhoneRequestDraft(
            house_id=body.house_id,
            category=body.category,
            description=body.description,
            flat_id=body.flat_id,
            caller_name=body.caller_name,
            caller_phone=body.caller_phone,
        ),
        current_org.user_id,
    )
    return _card(data, files_service)


@router.get("/admin/executors", summary="Исполнители организации")
async def list_org_executors(
    current_org: CurrentOrgDep,
    admin_requests_service: FromDishka[AdminRequestsService],
) -> list[ExecutorItem]:
    views = await admin_requests_service.executors(current_org.org_id)
    return [ExecutorItem.of(view) for view in views]
