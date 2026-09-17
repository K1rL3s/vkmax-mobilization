from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentResidencyDep, RequireConsentDep
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.requests import (
    CreateRequestRequest,
    RateRequestRequest,
    RepeatRequestRequest,
    RequestCard,
    RequestCategoryItem,
    RequestExport,
    RequestListItem,
    ReviewRequestRequest,
    SimilarRequestsResponse,
)
from zheka.core.enums import RequestCategory, RequestStatus
from zheka.core.ids import RequestId

router = APIRouter(tags=["Заявки"], route_class=DishkaRoute)


@router.get("/request-categories", summary="Категории заявок и нормативы")
async def list_request_categories(
    current_account: RequireConsentDep,
) -> list[RequestCategoryItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/requests", summary="Мои заявки")
async def list_my_requests(
    residency: CurrentResidencyDep,
    status: RequestStatus | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[RequestListItem]:
    raise NotImplementedError("ещё не реализовано")


@router.get("/requests/similar", summary="Соседи уже жаловались")
async def find_similar_requests(
    residency: CurrentResidencyDep,
    category: RequestCategory,
) -> SimilarRequestsResponse:
    raise NotImplementedError("ещё не реализовано")


@router.post("/requests", summary="Новая заявка")
async def create_request(
    residency: CurrentResidencyDep,
    body: CreateRequestRequest,
) -> RequestCard:
    raise NotImplementedError("ещё не реализовано")


@router.get("/requests/{request_id}", summary="Карточка заявки")
async def get_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
) -> RequestCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/requests/{request_id}/rating", summary="Оценить заявку")
async def rate_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
    body: RateRequestRequest,
) -> RequestCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/requests/{request_id}/repeat", summary="Повторная заявка")
async def create_repeat_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
    body: RepeatRequestRequest,
) -> RequestCard:
    raise NotImplementedError("ещё не реализовано")


@router.post("/requests/{request_id}/review", summary="Приемка работ жителем")
async def review_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
    body: ReviewRequestRequest,
) -> RequestCard:
    raise NotImplementedError("ещё не реализовано")


@router.get("/requests/{request_id}/export", summary="Данные заявки для печати")
async def export_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
) -> RequestExport:
    raise NotImplementedError("ещё не реализовано")
