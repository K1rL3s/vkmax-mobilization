from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from zheka.api.dependencies import CurrentResidencyDep, RequireConsentDep
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.files import FileRef
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
from zheka.core.enums import CATEGORY_RULES, RequestCategory, RequestStatus
from zheka.core.ids import RequestId
from zheka.core.services.files import FilesService
from zheka.core.services.requests import RequestCardData, RequestDraft, RequestsService

router = APIRouter(tags=["Заявки"], route_class=DishkaRoute)


def _card(card: RequestCardData, files_service: FilesService) -> RequestCard:
    return RequestCard.of(
        card,
        [
            FileRef(name=photo.path, url=files_service.sign(photo.path))
            for photo in card.issue_photos
        ],
        [
            FileRef(name=photo.path, url=files_service.sign(photo.path))
            for photo in card.result_photos
        ],
    )


@router.get("/request-categories", summary="Категории заявок и нормативы")
async def list_request_categories(
    current_account: RequireConsentDep,  # noqa: ARG001
) -> list[RequestCategoryItem]:
    # кнопки рисует фронт по этому списку, зашивать категории у себя ему нечем
    return [
        RequestCategoryItem.of(category, rule)
        for category, rule in CATEGORY_RULES.items()
    ]


@router.get("/requests", summary="Мои заявки")
async def list_my_requests(
    residency: CurrentResidencyDep,
    requests_service: FromDishka[RequestsService],
    status: RequestStatus | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[RequestListItem]:
    rows, total = await requests_service.list_mine(
        residency.user_id,
        residency.house_id,
        status,
        limit,
        offset,
    )
    return Page(items=[RequestListItem.of_row(row) for row in rows], total=total)


@router.get("/requests/similar", summary="Соседи уже жаловались")
async def find_similar_requests(
    residency: CurrentResidencyDep,
    category: RequestCategory,
) -> SimilarRequestsResponse:
    raise NotImplementedError("ещё не реализовано")


@router.post("/requests", summary="Новая заявка")
async def create_request(
    residency: CurrentResidencyDep,
    requests_service: FromDishka[RequestsService],
    files_service: FromDishka[FilesService],
    body: CreateRequestRequest,
) -> RequestCard:
    card = await requests_service.create(
        residency.user_id,
        residency.house_id,
        RequestDraft(
            category=body.category,
            description=body.description,
            flat_id=body.flat_id,
            photos=body.photos,
            group_id=body.join_group_id,
            llm_suggested=body.llm_suggested,
            llm_accepted=body.llm_accepted,
        ),
    )
    return _card(card, files_service)


@router.get("/requests/{request_id}", summary="Карточка заявки")
async def get_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
    requests_service: FromDishka[RequestsService],
    files_service: FromDishka[FilesService],
) -> RequestCard:
    card = await requests_service.get_card(current_account.user_id, request_id)
    return _card(card, files_service)


@router.post("/requests/{request_id}/rating", summary="Оценить заявку")
async def rate_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
    requests_service: FromDishka[RequestsService],
    files_service: FromDishka[FilesService],
    body: RateRequestRequest,
) -> RequestCard:
    card = await requests_service.rate(
        current_account.user_id,
        request_id,
        body.rating,
        body.feedback,
    )
    return _card(card, files_service)


@router.post("/requests/{request_id}/repeat", summary="Повторная заявка")
async def create_repeat_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
    requests_service: FromDishka[RequestsService],
    files_service: FromDishka[FilesService],
    body: RepeatRequestRequest,
) -> RequestCard:
    card = await requests_service.repeat(
        current_account.user_id,
        request_id,
        body.description,
        body.photos,
    )
    return _card(card, files_service)


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
