from collections.abc import Mapping, Sequence

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import EventType, NotificationCategory, NotificationLevel
from zheka.core.ids import AccessRequestId, HouseId, MaxChatId, RequestId, UserId
from zheka.core.notifications import DEFAULT_LEVEL
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
        self, user_id: UserId
    ) -> dict[NotificationCategory, NotificationLevel]:
        stored = await self._notifications.get_levels(user_id)
        return {
            category: stored.get(category, DEFAULT_LEVEL)
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
    ) -> None:
        self._publisher.publish(
            TaskName.SEND_TO_USER,
            user_id=user_id,
            text=text,
            category=category.value,
            mandatory=mandatory,
        )

    def notify_users(
        self,
        user_ids: Sequence[UserId],
        text: str,
        *,
        category: NotificationCategory,
        mandatory: bool,
    ) -> None:
        if not user_ids:
            return
        self._publisher.publish(
            TaskName.BROADCAST_TO_USERS,
            user_ids=list(user_ids),
            text=text,
            category=category.value,
            mandatory=mandatory,
        )

    def notify_chats(self, chat_ids: Sequence[MaxChatId], text: str) -> None:
        if not chat_ids:
            return
        self._publisher.publish(
            TaskName.BROADCAST_TO_CHATS, chat_ids=list(chat_ids), text=text
        )

    def open_executor_card(
        self, request_id: RequestId, user_id: UserId | None = None
    ) -> None:
        self._publisher.publish(
            TaskName.SEND_EXECUTOR_CARD, request_id=request_id, user_id=user_id
        )

    def open_review_card(self, request_id: RequestId) -> None:
        self._publisher.publish(TaskName.SEND_REVIEW_CARD, request_id=request_id)

    def welcome_chat(self, chat_id: MaxChatId, house_id: HouseId) -> None:
        self._publisher.publish(
            TaskName.WELCOME_CHAT, chat_id=chat_id, house_id=house_id
        )

    def open_access_slots(self, access_request_id: AccessRequestId) -> None:
        self._publisher.publish(
            TaskName.BROADCAST_ACCESS_REQUEST, access_request_id=access_request_id
        )

    def sync_chat_pins(self, chat_id: MaxChatId) -> None:
        self._publisher.publish(TaskName.SYNC_CHAT_PINS, chat_id=chat_id)
