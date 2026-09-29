from datetime import datetime
from typing import Self

from pydantic import Field

from zheka.api.dependencies import CurrentOrg
from zheka.api.schemas.base import BaseSchema, FreeText
from zheka.api.schemas.files import FILES_DESCRIPTION, FileRef
from zheka.core.enums import (
    CATEGORY_RULES,
    CategoryRule,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestGroupStatus,
    RequestStatus,
    ResponsibilityZone,
)
from zheka.core.ids import (
    FlatId,
    HouseId,
    RequestGroupId,
    RequestId,
    ResidentId,
    UserId,
)
from zheka.core.services.admin_requests import (
    AdminRequestCardData,
    AdminRequestRow,
    ExecutorView,
    RequestGroupCardData,
)
from zheka.core.services.request_groups import SimilarRequests
from zheka.core.services.requests import (
    MAX_RATING,
    MIN_RATING,
    RequestCardData,
    RequestMessageView,
    RequestRow,
)

UNKNOWN_AUTHOR = "Пользователь"
DEADLINE_TEXT = "Срок устранения, например «3 суток»"
DEADLINE_BASIS = "Норма права под сроком; пусто - срок сервиса, норматива нет"


class RequestCategoryItem(BaseSchema):
    category: RequestCategory
    label: str
    zone: ResponsibilityZone
    deadline_text: str = Field(description=DEADLINE_TEXT)
    react_text: str | None = Field(
        default=None,
        description="Срок реакции, например «30 минут»; пусто - не нормирован",
    )
    deadline_basis: str | None = Field(default=None, description=DEADLINE_BASIS)

    @classmethod
    def of(cls, category: RequestCategory, rule: CategoryRule) -> Self:
        return cls(
            category=category,
            label=rule.label,
            zone=rule.zone,
            deadline_text=rule.deadline_text,
            react_text=rule.react_text,
            deadline_basis=rule.basis,
        )


class RequestListItem(BaseSchema):
    id: RequestId
    created_at: datetime
    category: RequestCategory
    category_label: str
    description: str
    status: RequestStatus
    channel: RequestChannel
    has_photos: bool = Field(description="Есть вложения: фото или видео")
    group_size: int
    flat_number: str | None = None
    group_id: RequestGroupId | None = None
    executor_name: str | None = None
    rating: int | None = Field(default=None, description="Оценка жителя от 1 до 5")
    deadline_at: datetime | None = None
    completion_reason: RequestCompletionReason | None = None
    escalated_at: datetime | None = Field(
        default=None,
        description="Когда автор попросил руководство УК вмешаться",
    )

    @classmethod
    def of_row(cls, row: RequestRow) -> Self:
        request = row.request
        rule = CATEGORY_RULES[request.category]
        return cls(
            id=request.id,
            created_at=request.created_at,
            category=request.category,
            category_label=rule.label,
            description=request.description,
            status=request.status,
            channel=request.channel,
            has_photos=row.has_attachments,
            group_size=row.group_size,
            flat_number=None if row.flat is None else row.flat.number,
            group_id=request.group_id,
            executor_name=None if row.executor is None else row.executor.name,
            rating=request.rating,
            deadline_at=request.deadline_at,
            completion_reason=request.completion_reason,
            escalated_at=request.escalated_at,
        )


class RequestMessageItem(BaseSchema):
    created_at: datetime
    author_role: str
    author_name: str
    text: str
    is_internal: bool = Field(
        default=False,
        description="Заметка только для УК, например причина отказа исполнителя",
    )

    @classmethod
    def of(cls, view: RequestMessageView) -> Self:
        return cls(
            created_at=view.message.created_at,
            author_role=view.message.author_role,
            author_name=UNKNOWN_AUTHOR if view.author is None else view.author.name,
            text=view.message.text,
            is_internal=view.message.is_internal,
        )


class RequestStatusLogItem(BaseSchema):
    at: datetime
    to_status: RequestStatus
    by_role: str
    from_status: RequestStatus | None = None


class RequestCard(RequestListItem):
    house_id: HouseId
    address: str
    org_name: str | None
    deadline_text: str = Field(description=DEADLINE_TEXT)
    deadline_basis: str | None = Field(default=None, description=DEADLINE_BASIS)
    react_deadline_at: datetime | None = Field(
        default=None,
        description="Срок реакции (принять заявку); пусто - не нормирован",
    )
    photos: list[FileRef] = Field(description="Вложения проблемы: фото или видео")
    result_photos: list[FileRef] = Field(
        description="Вложения результата: фото или видео",
    )
    messages: list[RequestMessageItem]
    timeline: list[RequestStatusLogItem]
    can_review: bool
    can_rate: bool
    feedback: str | None = None
    parent_request_id: RequestId | None = None
    flat_id: FlatId | None = None
    auto_close_at: datetime | None = Field(
        default=None,
        description="Автозакрытие заявки, оставленной на приемке",
    )
    can_demo_expire: bool = Field(
        description="Автор заявки в демо-УК может перенести ее срок на текущий момент",
    )

    @classmethod
    def of(
        cls,
        card: RequestCardData,
        attachments: list[FileRef],
        result_attachments: list[FileRef],
    ) -> Self:
        request = card.request
        rule = CATEGORY_RULES[request.category]
        base = RequestListItem.of_row(
            RequestRow(
                request=request,
                flat=card.flat,
                has_attachments=bool(attachments),
                group_size=card.group_size,
                executor=card.executor,
            ),
        )
        return cls(
            **base.model_dump(),
            house_id=request.house_id,
            address=card.house.address,
            org_name=None if card.org is None else card.org.name,
            deadline_text=rule.deadline_text,
            deadline_basis=rule.basis,
            react_deadline_at=request.react_deadline_at,
            photos=attachments,
            result_photos=result_attachments,
            messages=[RequestMessageItem.of(view) for view in card.messages],
            timeline=[
                RequestStatusLogItem.model_validate(log) for log in card.timeline
            ],
            can_review=card.can_review,
            can_rate=card.can_rate,
            feedback=request.feedback,
            parent_request_id=request.parent_request_id,
            flat_id=request.flat_id,
            auto_close_at=card.auto_close_at,
            can_demo_expire=card.can_demo_expire,
        )


class CreateRequestRequest(BaseSchema):
    category: RequestCategory
    description: FreeText
    flat_id: FlatId | None = None
    photos: list[str] = Field(default_factory=list, description=FILES_DESCRIPTION)
    join_group_id: RequestGroupId | None = None
    llm_suggested: bool = False
    llm_accepted: bool = False


class SimilarRequestsResponse(BaseSchema):
    category: RequestCategory
    neighbours_count: int
    can_join: bool
    group_id: RequestGroupId | None = None
    window_started_at: datetime | None = None

    @classmethod
    def of(cls, similar: SimilarRequests) -> Self:
        return cls(
            category=similar.category,
            neighbours_count=similar.flats_count,
            can_join=similar.group_id is not None,
            group_id=similar.group_id,
            window_started_at=similar.window_started_at,
        )


class RateRequestRequest(BaseSchema):
    rating: int = Field(ge=MIN_RATING, le=MAX_RATING)
    feedback: FreeText | None = None


class RepeatRequestRequest(BaseSchema):
    description: FreeText | None = None
    photos: list[str] = Field(default_factory=list, description=FILES_DESCRIPTION)


class RequestExport(BaseSchema):
    request: RequestCard
    disclaimer: str


class SharedRequestResponse(BaseSchema):
    posted: bool = Field(
        description="Карточка ушла в привязанный чат дома; иначе поделиться вручную",
    )
    share_text: str = Field(description="Текст для нативного шеринга MAX")
    share_link: str = Field(description="Ссылка «У меня тоже» на форму заявки")


class AdminRequestListItem(RequestListItem):
    house_id: HouseId
    address: str
    is_staff_author: bool
    author_name: str | None = None
    author_phone: str | None = None
    caller_name: str | None = None
    caller_phone: str | None = None

    @classmethod
    def of_admin(cls, row: AdminRequestRow, viewer: CurrentOrg) -> Self:
        base = RequestListItem.of_row(row)
        request = row.request
        return cls(
            **base.model_dump(exclude={"escalated_at"}),
            escalated_at=row.escalated_at,
            house_id=request.house_id,
            address=row.house.address,
            is_staff_author=request.is_staff_author,
            author_name=None if row.author is None else row.author.name,
            author_phone=viewer.phone_of(row.author),
            caller_name=request.caller_name,
            caller_phone=request.caller_phone,
        )


class AdminRequestCard(RequestCard):
    is_staff_author: bool
    author_name: str | None = None
    author_phone: str | None = None
    caller_name: str | None = None
    caller_phone: str | None = None
    executor_user_id: UserId | None = None

    @classmethod
    def of_admin(
        cls,
        data: AdminRequestCardData,
        attachments: list[FileRef],
        result_attachments: list[FileRef],
        viewer: CurrentOrg,
    ) -> Self:
        base = RequestCard.of(data.card, attachments, result_attachments)
        request = data.card.request
        return cls(
            **base.model_dump(),
            is_staff_author=request.is_staff_author,
            author_name=None if data.author is None else data.author.name,
            author_phone=viewer.phone_of(data.author),
            caller_name=request.caller_name,
            caller_phone=request.caller_phone,
            executor_user_id=request.executor_user_id,
        )


class ChangeRequestStatusRequest(BaseSchema):
    status: RequestStatus
    comment: FreeText | None = None


class ReplyToRequestRequest(BaseSchema):
    text: FreeText


class AssignExecutorRequest(BaseSchema):
    user_id: UserId


class CreatePhoneRequestRequest(BaseSchema):
    house_id: HouseId
    category: RequestCategory
    description: FreeText
    flat_id: FlatId | None = None
    caller_name: FreeText | None = None
    caller_phone: FreeText | None = None
    resident_id: ResidentId | None = Field(
        default=None,
        description=(
            "Житель дома, от чьего имени заявка: он становится ее автором, "
            "получает уведомления, принимает и оценивает работу. Квартира - "
            "его, имя и телефон звонившего тогда необязательны"
        ),
    )


class RequestGroupCard(BaseSchema):
    id: RequestGroupId
    house_id: HouseId
    address: str
    category: RequestCategory
    category_label: str
    status: RequestGroupStatus
    window_started_at: datetime
    flats_count: int
    requests: list[AdminRequestListItem]

    @classmethod
    def of(cls, data: RequestGroupCardData, viewer: CurrentOrg) -> Self:
        group = data.group
        return cls(
            id=group.id,
            house_id=group.house_id,
            address=data.house.address,
            category=group.category,
            category_label=CATEGORY_RULES[group.category].label,
            status=group.status,
            window_started_at=group.window_started_at,
            flats_count=data.flats_count,
            requests=[AdminRequestListItem.of_admin(row, viewer) for row in data.rows],
        )


class ChangeGroupStatusRequest(BaseSchema):
    status: RequestStatus
    comment: FreeText | None = None


class ExecutorItem(BaseSchema):
    user_id: UserId
    name: str
    username: str | None
    active_requests: int

    @classmethod
    def of(cls, view: ExecutorView) -> Self:
        return cls(
            user_id=view.user.id,
            name=view.user.name,
            username=view.user.username,
            active_requests=view.active_requests,
        )


class ClassifyRequestRequest(BaseSchema):
    text: str = Field(max_length=4000, description="Описание проблемы жителем")


class ClassifyRequestResponse(BaseSchema):
    category: RequestCategory | None
    zone: ResponsibilityZone | None

    @classmethod
    def of(cls, category: RequestCategory | None) -> Self:
        return cls(
            category=category,
            zone=None if category is None else CATEGORY_RULES[category].zone,
        )
