from collections.abc import Sequence
from datetime import UTC, datetime

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter
from maxo import Bot
from maxo.utils.deeplink import create_startapp_link

from zheka.api.dependencies import CurrentResidencyDep, RequireConsentDep
from zheka.api.schemas.base import Limit, Offset, Page
from zheka.api.schemas.files import FileRef
from zheka.api.schemas.requests import (
    ClassifyRequestRequest,
    ClassifyRequestResponse,
    CreateRequestRequest,
    RateRequestRequest,
    RepeatRequestRequest,
    RequestCard,
    RequestCategoryItem,
    RequestExport,
    RequestListItem,
    SharedRequestResponse,
    SimilarRequestsResponse,
)
from zheka.core.deeplinks import house_category_payload
from zheka.core.enums import CATEGORY_RULES, RequestCategory, RequestStatus
from zheka.core.ids import RequestId
from zheka.core.models import RequestPhoto
from zheka.core.services.files import FilesService
from zheka.core.services.requests import RequestCardData, RequestDraft, RequestsService
from zheka.core.texts import REQUEST_EXPORT_DISCLAIMER, request_share_text
from zheka.infra.yandex import YandexQuota

router = APIRouter(tags=["Заявки"], route_class=DishkaRoute)


def signed(
    photos: Sequence[RequestPhoto],
    files_service: FilesService,
) -> list[FileRef]:
    return [FileRef.signed(photo.path, files_service) for photo in photos]


def _card(card: RequestCardData, files_service: FilesService) -> RequestCard:
    return RequestCard.of(
        card,
        signed(card.issue_photos, files_service),
        signed(card.result_photos, files_service),
    )


@router.get("/request-categories", summary="Категории заявок и нормативы")
async def list_request_categories(
    current_account: RequireConsentDep,  # noqa: ARG001
) -> list[RequestCategoryItem]:
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
    requests_service: FromDishka[RequestsService],
    category: RequestCategory,
) -> SimilarRequestsResponse:
    similar = await requests_service.similar(
        residency.user_id,
        residency.house_id,
        category,
    )
    return SimilarRequestsResponse.of(similar)


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
            **body.model_dump(exclude={"join_group_id"}),
            group_id=body.join_group_id,
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


@router.post("/requests/{request_id}/accept", summary="Принять работу")
async def accept_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
    requests_service: FromDishka[RequestsService],
    files_service: FromDishka[FilesService],
) -> RequestCard:
    card = await requests_service.accept(current_account.user_id, request_id)
    return _card(card, files_service)


@router.get("/requests/{request_id}/export", summary="Данные заявки для печати")
async def export_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
    requests_service: FromDishka[RequestsService],
    files_service: FromDishka[FilesService],
) -> RequestExport:
    card = await requests_service.export(current_account.user_id, request_id)
    return RequestExport(
        request=_card(card, files_service),
        disclaimer=REQUEST_EXPORT_DISCLAIMER,
    )


@router.post(
    "/requests/{request_id}/chat-card",
    summary="Рассказать соседям о заявке",
    description=(
        "Только автор и только заявка до приемки. Если у дома есть привязанный "
        "чат с ботом-администратором, туда уходит карточка заявки (или общей "
        "заявки дома, если заявка в нее вошла), иначе клиент открывает шеринг"
    ),
)
async def share_request_to_chat(
    request_id: RequestId,
    current_account: RequireConsentDep,
    requests_service: FromDishka[RequestsService],
    bot: FromDishka[Bot],
) -> SharedRequestResponse:
    shared = await requests_service.share_to_chat(current_account.user_id, request_id)
    request = shared.request
    return SharedRequestResponse(
        posted=shared.posted,
        share_text=request_share_text(request, shared.house),
        share_link=create_startapp_link(
            bot,
            house_category_payload(request.house_id, request.category),
        ),
    )


@router.post("/requests/classify", summary="Подсказать категорию по описанию")
async def classify_request_text(
    current_account: RequireConsentDep,
    requests_service: FromDishka[RequestsService],
    body: ClassifyRequestRequest,
    quota: FromDishka[YandexQuota],
) -> ClassifyRequestResponse:
    if not quota.take(current_account.user_id):
        return ClassifyRequestResponse.of(None)
    category = await requests_service.classify(current_account.user_id, body.text)
    return ClassifyRequestResponse.of(category)


@router.post(
    "/requests/{request_id}/demo/expire",
    summary="Демо: срок заявки истек",
    description=(
        "Только автор заявки в демо-УК, пока заявка открыта и не просрочена, "
        "иначе 404. Срок, и срок реакции, если он позже, становится минутой "
        "раньше текущего момента, уведомления о просрочке уходят сразу"
    ),
)
async def expire_request_deadline(
    request_id: RequestId,
    current_account: RequireConsentDep,
    requests_service: FromDishka[RequestsService],
    files_service: FromDishka[FilesService],
) -> RequestCard:
    card = await requests_service.demo_expire(
        current_account.user_id,
        request_id,
        datetime.now(UTC),
    )
    return _card(card, files_service)


@router.post(
    "/requests/{request_id}/escalate",
    summary="Попросить руководство УК вмешаться",
    description=(
        "Только автор просроченной открытой заявки, один раз: сотрудники УК и "
        "исполнитель получают сообщение, автор - подтверждение, заявка "
        "встает первой во входящих. Повтор или непросроченная заявка - 409, "
        "чужая - 404"
    ),
)
async def escalate_request(
    request_id: RequestId,
    current_account: RequireConsentDep,
    requests_service: FromDishka[RequestsService],
    files_service: FromDishka[FilesService],
) -> RequestCard:
    card = await requests_service.escalate(
        current_account.user_id,
        request_id,
        datetime.now(UTC),
    )
    return _card(card, files_service)
