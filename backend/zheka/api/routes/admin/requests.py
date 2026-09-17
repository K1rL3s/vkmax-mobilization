from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentOrgDep
from zheka.api.schemas.base import Limit, Offset, Page
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
from zheka.core.ids import HouseId, RequestGroupId, RequestId

router = APIRouter(tags=["Админка: заявки"], route_class=DishkaRoute)


@router.get("/admin/requests", summary="Входящие заявки организации")
async def list_org_requests(
    current_org: CurrentOrgDep,
    status: RequestStatus | None = None,
    category: RequestCategory | None = None,
    channel: RequestChannel | None = None,
    house_id: HouseId | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AdminRequestListItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/requests/{request_id}", summary="Карточка заявки в админке")
async def get_org_request(
    request_id: RequestId,
    current_org: CurrentOrgDep,
) -> AdminRequestCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/admin/requests/{request_id}/status", summary="Сменить статус заявки")
async def change_request_status(
    request_id: RequestId,
    current_org: CurrentOrgDep,
    body: ChangeRequestStatusRequest,
) -> AdminRequestCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/admin/requests/{request_id}/reply", summary="Ответить жителю")
async def reply_to_request(
    request_id: RequestId,
    current_org: CurrentOrgDep,
    body: ReplyToRequestRequest,
) -> AdminRequestCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/admin/requests/{request_id}/assign", summary="Назначить исполнителя")
async def assign_request_executor(
    request_id: RequestId,
    current_org: CurrentOrgDep,
    body: AssignExecutorRequest,
) -> AdminRequestCard:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/request-groups/{group_id}", summary="Группа заявок")
async def get_request_group(
    group_id: RequestGroupId,
    current_org: CurrentOrgDep,
) -> RequestGroupCard:
    raise NotImplementedError("ещё не реализовано")


@router.post(
    "/admin/request-groups/{group_id}/status",
    summary="Сменить статус всей группе",
)
async def change_request_group_status(
    group_id: RequestGroupId,
    current_org: CurrentOrgDep,
    body: ChangeGroupStatusRequest,
) -> RequestGroupCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/admin/requests/phone", summary="Заявка по звонку")
async def create_phone_request(
    current_org: CurrentOrgDep,
    body: CreatePhoneRequestRequest,
) -> AdminRequestCard:
    raise NotImplementedError("ещё не реализовано")


@router.get("/admin/executors", summary="Исполнители организации")
async def list_org_executors(current_org: CurrentOrgDep) -> list[ExecutorItem]:
    raise NotImplementedError("ещё не реализовано")
