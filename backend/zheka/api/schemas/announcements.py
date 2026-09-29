from collections.abc import Mapping
from datetime import datetime
from typing import Self

from pydantic import Field

from zheka.api.schemas.base import BaseSchema
from zheka.core.enums import (
    AnnouncementChannel,
    NoticeStatus,
    RequestCategory,
    ResidentRole,
)
from zheka.core.ids import AnnouncementId, FlatId, HouseId, PollId
from zheka.core.models import Announcement, NoticeDelivery
from zheka.core.services.announcements import (
    ANNOUNCEMENT_TEXT_LIMIT,
    ActiveWorks,
    AnnouncementData,
    NoticeRegisterData,
    WorksDraft,
)
from zheka.core.services.files import FilesService

DOCUMENTS_LIMIT = 5
DOCUMENT_TITLE_LIMIT = 120


class AnnouncementWorks(BaseSchema):
    category: RequestCategory | None = Field(
        description="Категория заявок, в форме которых житель увидит предупреждение",
    )
    starts_at: datetime
    ends_at: datetime = Field(
        description="Окончание; после «Завершить досрочно» - момент завершения",
    )

    @classmethod
    def of(cls, announcement: Announcement) -> Self | None:
        if announcement.works_from is None or announcement.works_until is None:
            return None
        return cls(
            category=announcement.works_category,
            starts_at=announcement.works_from,
            ends_at=announcement.works_until,
        )


class AnnouncementDocument(BaseSchema):
    name: str
    title: str
    url: str

    @classmethod
    def signed(cls, document: Mapping[str, str], files: FilesService) -> Self:
        return cls(
            name=document["name"],
            title=document["title"],
            url=files.sign(document["name"]),
        )


class AnnouncementItem(BaseSchema):
    id: AnnouncementId
    created_at: datetime
    text: str
    house_ids: list[HouseId]
    channels: list[AnnouncementChannel]
    org_name: str | None = None
    recipients_count: int = Field(
        default=0,
        description=(
            "Сколько адресатов было на момент отправки: по одному на жителя "
            "для канала direct и по одному на привязанный чат для канала chat"
        ),
    )
    delivered_count: int | None = Field(
        description=(
            "Скольким адресатам MAX принял сообщение, по всем каналам вместе. "
            "null, пока рассылка идет, и у объявлений, отправленных до "
            "появления отчета"
        ),
    )
    houses_without_chat: list[HouseId] = Field(
        default_factory=list,
        description=(
            "Дома, у которых не привязан чат, поэтому объявление туда не ушло. "
            "Заполняется только при создании объявления"
        ),
    )
    urgent: bool = Field(
        default=False,
        description="Срочное: авария, отключение. Житель видит его выделенным",
    )
    entrances: list[int] | None = Field(
        default=None,
        description="Подъезды, которым адресовано объявление; null - всему дому",
    )
    flats_count: int | None = Field(
        default=None,
        description="Скольким квартирам адресовано объявление; null - не квартирам",
    )
    poll_id: PollId | None = Field(
        default=None,
        description="Опрос, о котором это объявление сообщает жителям",
    )
    works: AnnouncementWorks | None = Field(
        default=None,
        description="Плановые работы, о которых объявление; null - обычное объявление",
    )
    documents: list[AnnouncementDocument] = Field(
        default_factory=list,
        description="Документы PDF к объявлению: приказ, график",
    )

    @classmethod
    def of(cls, data: AnnouncementData, files: FilesService) -> Self:
        announcement = data.announcement
        return cls(
            id=announcement.id,
            created_at=announcement.created_at,
            text=announcement.text,
            house_ids=announcement.house_ids,
            channels=[
                AnnouncementChannel(channel) for channel in announcement.channels
            ],
            org_name=data.org_name,
            recipients_count=announcement.recipients_count,
            delivered_count=announcement.delivered_count,
            houses_without_chat=list(data.houses_without_chat),
            urgent=announcement.urgent,
            entrances=announcement.entrances,
            flats_count=announcement.flats_count,
            poll_id=announcement.poll_id,
            works=AnnouncementWorks.of(announcement),
            documents=[
                AnnouncementDocument.signed(document, files)
                for document in announcement.documents
            ],
        )


class WorksInput(BaseSchema):
    category: RequestCategory | None = None
    starts_at: datetime = Field(description="Начало, местное время первого дома")
    ends_at: datetime = Field(description="Окончание, местное время первого дома")

    def draft(self) -> WorksDraft:
        return WorksDraft(
            category=self.category,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
        )


class DocumentInput(BaseSchema):
    name: str = Field(description="Имя файла из upload_document, не ссылка")
    title: str = Field(min_length=1, max_length=DOCUMENT_TITLE_LIMIT)


class CreateAnnouncementRequest(BaseSchema):
    house_ids: list[HouseId]
    text: str = Field(
        description=f"Текст объявления, до {ANNOUNCEMENT_TEXT_LIMIT} символов",
    )
    channels: list[AnnouncementChannel] = Field(
        default_factory=lambda: [AnnouncementChannel.CHAT],
    )
    urgent: bool = Field(
        default=False,
        description="Срочное: авария, отключение. Житель видит его выделенным",
    )
    entrances: list[int] | None = Field(
        default=None,
        min_length=1,
        description=(
            "Только эти подъезды одного дома: личные сообщения получат жители, "
            "у которых указана квартира в этих подъездах; null - весь дом"
        ),
    )
    flat_ids: list[FlatId] | None = Field(
        default=None,
        min_length=1,
        description=(
            "Только эти квартиры одного дома: личные сообщения получат их "
            "подтвержденные жители, в чат дома такое объявление не уходит; "
            "null - весь дом"
        ),
    )
    works: WorksInput | None = Field(
        default=None,
        description=(
            "Плановые работы: жители увидят срок, форма заявки - предупреждение"
        ),
    )
    documents: list[DocumentInput] = Field(
        default_factory=list,
        max_length=DOCUMENTS_LIMIT,
        description=f"До {DOCUMENTS_LIMIT} документов PDF из upload_document",
    )


class NoticeRecipient(BaseSchema):
    role: ResidentRole | None = Field(
        description="Собственник или арендатор; null - автор демо-объявления вне дома",
    )
    verified: bool
    status: NoticeStatus = Field(
        description=(
            "pending - рассылка не дошла до жителя: первые 10 минут идет, потом "
            "нет данных; delivered - MAX принял сообщение, прочтение MAX не "
            "сообщает; failed - MAX отказал; muted - житель выключил объявления; "
            "bot_stopped - житель остановил бота"
        ),
    )
    at: datetime | None = Field(description="Когда стал известен статус")

    @classmethod
    def of(cls, delivery: NoticeDelivery) -> Self:
        return cls(
            role=delivery.role,
            verified=delivery.verified,
            status=delivery.status,
            at=delivery.at,
        )


class NoticeRegisterFlat(BaseSchema):
    flat_id: FlatId
    number: str
    entrance: int | None
    recipients: list[NoticeRecipient] = Field(
        description="Жители сервиса на момент отправки; пусто - нет в сервисе",
    )
    delivered: bool = Field(description="Хотя бы одному жителю MAX доставил")


class NoticeRegister(BaseSchema):
    announcement: AnnouncementItem
    house_id: HouseId
    address: str
    flats: list[NoticeRegisterFlat] = Field(
        description="Квартиры дома, которым адресовано объявление, по порядку номеров",
    )
    without_flat: list[NoticeRecipient] = Field(
        description="Адресаты в этом доме, не указавшие квартиру",
    )
    flats_delivered: int
    chat_delivered: int | None = Field(
        description=(
            "Скольким чатам домов объявления MAX принял сообщение; null, пока "
            "рассылка идет. По квартирам чат не раскладывается"
        ),
    )
    generated_at: datetime
    is_demo: bool

    @classmethod
    def of(
        cls,
        data: NoticeRegisterData,
        files: FilesService,
        *,
        is_demo: bool,
    ) -> Self:
        return cls(
            announcement=AnnouncementItem.of(data.announcement, files),
            house_id=data.house.id,
            address=data.house.address,
            flats=[
                NoticeRegisterFlat(
                    flat_id=item.flat.id,
                    number=item.flat.number,
                    entrance=item.flat.entrance,
                    recipients=[NoticeRecipient.of(row) for row in item.deliveries],
                    delivered=item.delivered,
                )
                for item in data.flats
            ],
            without_flat=[NoticeRecipient.of(row) for row in data.without_flat],
            flats_delivered=data.flats_delivered,
            chat_delivered=data.announcement.announcement.delivered_chat,
            generated_at=data.generated_at,
            is_demo=is_demo,
        )


class PlannedWorks(BaseSchema):
    announcement_id: AnnouncementId
    title: str = Field(description="Первая строка объявления")
    ends_at: datetime

    @classmethod
    def of(cls, works: ActiveWorks) -> Self:
        return cls(
            announcement_id=works.announcement.id,
            title=works.announcement.text.split("\n", 1)[0],
            ends_at=works.ends_at,
        )
