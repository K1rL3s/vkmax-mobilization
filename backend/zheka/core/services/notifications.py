from collections.abc import Mapping, Sequence

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core import texts
from zheka.core.deeplinks import request_app_path
from zheka.core.enums import (
    ChatCardKind,
    EventType,
    NotificationCategory,
    NotificationLevel,
)
from zheka.core.ids import (
    AccessRequestId,
    AnnouncementId,
    HouseId,
    MaxChatId,
    RequestId,
    UserId,
)
from zheka.core.models import Request
from zheka.core.notifications import default_level
from zheka.core.services.events import EventsService
from zheka.infra.database.repos.notifications import NotificationsRepo


class NotificationsService:
    __slots__ = ("_events", "_notifications", "_publisher")

    def __init__(
        self,
        notifications_repo: NotificationsRepo,
        publisher: TaskPublisher,
        events_service: EventsService,
    ) -> None:
        self._notifications = notifications_repo
        self._publisher = publisher
        self._events = events_service

    async def levels(
        self,
        user_id: UserId,
    ) -> dict[NotificationCategory, NotificationLevel]:
        stored = await self._notifications.get_levels(user_id)
        return {
            category: stored.get(category, default_level(category))
            for category in NotificationCategory
        }

    async def update(
        self,
        user_id: UserId,
        settings: Mapping[NotificationCategory, NotificationLevel],
    ) -> dict[NotificationCategory, NotificationLevel]:
        for category, level in settings.items():
            if await self._notifications.set_level(user_id, category, level):
                await self._events.record(
                    EventType.NOTIFICATION_SETTINGS_CHANGED,
                    user_id=user_id,
                    category=category.value,
                    level=level.value,
                )
        return await self.levels(user_id)

    def notify_user(
        self,
        user_id: UserId,
        text: str,
        *,
        category: NotificationCategory,
        mandatory: bool,
        app_button: str | None = None,
        app_path: str | None = None,
    ) -> None:
        self._publisher.publish(
            TaskName.SEND_TO_USER,
            user_id=user_id,
            text=text,
            category=category.value,
            mandatory=mandatory,
            app_button=app_button,
            app_path=app_path,
        )

    def notify_users(
        self,
        user_ids: Sequence[UserId],
        text: str,
        *,
        category: NotificationCategory,
        mandatory: bool,
        app_button: str | None = None,
        app_path: str | None = None,
        announcement_id: AnnouncementId | None = None,
    ) -> None:
        if not user_ids:
            return
        self._publisher.publish(
            TaskName.BROADCAST_TO_USERS,
            user_ids=list(user_ids),
            text=text,
            category=category.value,
            mandatory=mandatory,
            app_button=app_button,
            app_path=app_path,
            announcement_id=announcement_id,
        )

    def notify_chats(
        self,
        chat_ids: Sequence[MaxChatId],
        text: str,
        *,
        app_button: str | None = None,
        app_path: str | None = None,
        announcement_id: AnnouncementId | None = None,
        reply_card: tuple[ChatCardKind, int] | None = None,
    ) -> None:
        if not chat_ids:
            return
        self._publisher.publish(
            TaskName.BROADCAST_TO_CHATS,
            chat_ids=list(chat_ids),
            text=text,
            app_button=app_button,
            app_path=app_path,
            announcement_id=announcement_id,
            **(
                {}
                if reply_card is None
                else {"card_kind": reply_card[0], "card_ref_id": reply_card[1]}
            ),
        )

    def open_executor_card(
        self,
        request_id: RequestId,
        user_id: UserId | None = None,
    ) -> None:
        self._publisher.publish(
            TaskName.SEND_EXECUTOR_CARD,
            request_id=request_id,
            user_id=user_id,
        )

    def open_review_card(self, request_id: RequestId) -> None:
        self._publisher.publish(TaskName.SEND_REVIEW_CARD, request_id=request_id)

    def welcome_chat(
        self,
        chat_id: MaxChatId,
        house_id: HouseId,
        *,
        member: str | None = None,
    ) -> None:
        self._publisher.publish(
            TaskName.WELCOME_CHAT,
            chat_id=chat_id,
            house_id=house_id,
            member=member,
        )

    def open_access_slots(self, access_request_id: AccessRequestId) -> None:
        self._publisher.publish(
            TaskName.BROADCAST_ACCESS_REQUEST,
            access_request_id=access_request_id,
        )

    def sync_chat_pins(
        self,
        chat_id: MaxChatId,
        *,
        notify: bool,
        resend: bool = False,
    ) -> None:
        self._publisher.publish(
            TaskName.SYNC_CHAT_PINS,
            chat_id=chat_id,
            notify=notify,
            resend=resend,
        )

    def sync_chat_card(self, kind: ChatCardKind, ref_id: int, *, post: bool) -> None:
        self._publisher.publish(
            TaskName.SYNC_CHAT_CARD,
            kind=kind,
            ref_id=ref_id,
            post=post,
        )

    def notify_author(self, request: Request, text: str) -> None:
        if request.author_user_id is not None:
            self.notify_user(
                request.author_user_id,
                text,
                category=NotificationCategory.REQUESTS,
                mandatory=True,
                app_button=texts.OPEN_REQUEST,
                app_path=request_app_path(request.id),
            )

    def send_gji_pdf(self, user_id: UserId, request_id: RequestId) -> None:
        self._publisher.publish(
            TaskName.SEND_GJI_PDF,
            user_id=user_id,
            request_id=request_id,
        )
